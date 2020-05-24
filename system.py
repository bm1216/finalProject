import psutil
import socket
import requests
from app import logger

SET_NAME = "containers"
ONE_MB = 1024.0 * 1024.0

# -------------------------------------
# UNDERLYING SYSTEM
# -------------------------------------

def get_resources():
  # We need to execute this once initially or it returns 0.0
  psutil.cpu_percent(percpu=True, interval=None)
  cpu_pct_per_cpu = psutil.cpu_percent(percpu=True)
  mem = psutil.virtual_memory()
  logger.info(mem)
  cpu_free_per_cpu = [(100 - util)/float(100) for util in cpu_pct_per_cpu]
  return cpu_free_per_cpu, mem.available


def register_this_container(db):
  """
  Registers this container in the shared database. This allows other
  containers to look it up and send functions to it
  """

  # Get container id.
  # bash_command = """head -1 /proc/self/cgroup|cut -d/ -f3"""
  # output = str(subprocess.check_output(['bash','-c', bash_command]), "utf-8").strip()

  # logger.info(output)

  my_host_name = socket.gethostname()
  my_ip = socket.gethostbyname(my_host_name)
  free_cpu, free_mem = get_resources()

  logger.info({"host_name": my_host_name, "ip": my_ip})

  pipe = db.pipeline()
  pipe.sadd(SET_NAME, my_ip).hmset(my_ip, {
      "host_id": my_host_name, "cpu": free_cpu, "mem": free_mem})
  pipe.execute()


def update_resources_for_this_host(db):
  """
  Registers this container's resources in the shared database.
  """
  my_host_name = socket.gethostname()
  my_ip = socket.gethostbyname(my_host_name)
  free_cpu, free_mem = get_resources()

  logger.info("UPDATING", extra = {"host_name": my_host_name, "ip": my_ip})

  pipe = db.pipeline()
  pipe.hmset(my_ip, {"cpu": free_cpu, "mem": free_mem})
  pipe.execute()

def check_resources(reqs):
  """
  Get current free resources and checks if this host has enough resources
  """
  logger.info("REQUIREMENTS: " + str(reqs))
  free_cpu, free_mem = get_resources()
  return check_if_free_resources(free_mem, free_cpu, reqs)


def check_if_free_resources(mem, cpu_free_per_cpu, reqs):
  """
  Checks if both memory and cpu constraints are satisfied.
  """
  req_mem = float(''.join(filter(str.isdigit, reqs["mem"])))
  if (mem.available/ONE_MB > req_mem):
    logger.info("MEM AVAILABLE: " + str(mem.available/ONE_MB))
    for free in cpu_free_per_cpu:
      logger.info("FREE: " + str(free))
      if (free > float(reqs["cpu"])):
        return True
    return False
  else:
    return False


def find_best_container_for_func(db, func_name, reqs):
  """
  Find the best container to execute this function.
  Using the sort(filter()) technique to find the best container.
  """
  containers = db.smembers(SET_NAME)
  valid_containers = []

  # Get a list of valid containers.
  for container in containers:
    logger.info(container)
    container_info = db.hgetall(container)

    if (check_if_free_resources(container_info.mem, container_info.cpu, reqs)):
      valid_containers.append(container)

  # For now just return the first valid container.
  return None if not valid_containers else valid_containers[0]

def execute_function_on_host(db, best_host, func_name):
  """
  Executes the function on another host
  """
  r = requests.get("{best_host}", json={"func": func_name})
  return r.content

def request_more_resources():
  """
  Asks knative for more application resources, because we think we've run out
  """
  logger.info("NEED MORE RESOURCES!!!!")