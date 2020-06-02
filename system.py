import psutil
import socket
import requests
from logger import logger

SET_NAME = "containers"
ONE_MB = 1024.0 * 1024.0

# -------------------------------------
# UNDERLYING SYSTEM
# -------------------------------------

def get_resources():
  # We need to execute this once initially or it returns 0.0
  cpu_pct_per_cpu = psutil.cpu_percent(percpu=True)
  mem = psutil.virtual_memory()
  logger.info(mem)
  free_cpu = 0
  for util in cpu_pct_per_cpu:
    free_cpu = free_cpu + (100 - util)/float(100)

  return free_cpu, mem.available


def register_this_container(cache, db):
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
  cache["ip"] = my_ip
  cache["host"] = my_host_name

  free_cpu, free_mem = get_resources()

  logger.info({"host_name": my_host_name, "ip": my_ip})
  try:
    pipe = db.pipeline()
    pipe.sadd(SET_NAME, my_ip).hmset(my_ip, {
        "host_id": my_host_name, "cpu": free_cpu, "mem": free_mem})
    pipe.execute()
  except Exception as e:
    logger.error(e)
    raise e


def update_resources_for_this_host(cache, db):
  """
  Registers this container's resources in the shared database.
  """
  free_cpu, free_mem = get_resources()
  my_ip = cache["ip"]

  logger.info("UPDATING", extra = {"cpu": free_cpu, "mem": free_mem, "ip": my_ip})
  try:
     db.hmset(my_ip, {"cpu": free_cpu, "mem": free_mem})
  except Exception as e:
    logger.error(e)
    raise e  


def check_resources(reqs):
  """
  Get current free resources and checks if this host has enough resources
  """
  logger.info("REQUIREMENTS: " + str(reqs))
  free_cpu, free_mem = get_resources()
  return check_if_free_resources(free_mem, free_cpu, reqs)


def check_if_free_resources(free_mem, free_cpu, reqs):
  """
  Checks if both memory and cpu constraints are satisfied.
  """
  req_mem = float(''.join(filter(str.isdigit, reqs["mem"])))
  logger.info("CHECK FOR RESOURCES", extra={"mem": free_mem, "cpu": free_cpu, "req_mem": req_mem})
  if (free_mem/ONE_MB > req_mem and free_cpu > float(reqs["cpu"])):
    logger.info("MEM AVAILABLE: " + str(free_mem/ONE_MB))
    logger.info("CPU FREE: " + str(free_cpu))
    return True
  else:
    logger.info("FAILED RESOURCE REQUIREMENTS")
    return False


def find_best_container_for_func(cache, db, reqs):
  """
  Find the best container to execute this function.
  Using the sort(filter()) technique to find the best container.
  """
  valid_containers = []
  my_ip = cache["ip"]

  containers = db.smembers(SET_NAME)
  containers.remove(my_ip)
  
  logger.info("CONTAINERS: " + str(containers))

  # Get a list of valid containers.
  for container in containers:
    container = str(container)
    logger.info(container)
    try:
      container_info = db.hgetall(container)
      logger.info(container_info)
    except Exception as e:
      logger.error(e)
      raise e

    logger.info("INFO", extra={"cpu": container_info["cpu"], "mem": container_info["mem"]})

    if (check_if_free_resources(float(container_info["mem"]), float(container_info["cpu"]), reqs)):
      valid_containers.append(container)

  logger.info("THESE ARE THE BEST CONTAINERS", extra={"valid_containers": valid_containers})

  # For now just return the first valid container.
  return None if not valid_containers else valid_containers[0]

def execute_function_on_host(best_host, func_name):
  """
  Executes the function on another host
  """
  logger.info("SENDING request to best host.")
  r = requests.get("http://{}:8080/".format(best_host), json={"func": func_name})
  logger.info(r)
  if (r.status_code != 200):
    raise Exception("Could not execute function on host {}".format(best_host))
  return r.content

def request_more_resources():
  """
  Asks knative for more application resources, because we think we've run out
  """
  logger.info("NEED MORE RESOURCES!!!!")