import os

from flask import Flask, request
import redis
import subprocess
import functools
import argparse
import time
from os import remove, makedirs
from os.path import exists, join
from time import sleep
import logging
from pythonjsonlogger import jsonlogger
import sys
import signal
import socket
import requests
import functions 

import psutil
from datetime import datetime

# Adapted from the hello world Python found at
# https://knative.dev/docs/serving/samples/hello-world/helloworld-python/

app = Flask(__name__)
SET_NAME = "containers"


class CustomJsonFormatter(jsonlogger.JsonFormatter):
  def add_fields(self, log_record, record, message_dict):
    super(CustomJsonFormatter, self).add_fields(
        log_record, record, message_dict)
    if not log_record.get('timestamp'):
      # this doesn't use record.created, so it is slightly off
      now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
      log_record['timestamp'] = now
    if log_record.get('level'):
      log_record['level'] = log_record['level'].upper()
    else:
      log_record['level'] = record.levelname


formatter = CustomJsonFormatter('(timestamp) (level) (name) (message)')

# init the logger as usual
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'DEBUG'))
logHandler = logging.StreamHandler()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


db = redis.Redis(host=os.environ.get('REDIS_HOST', 'redis'))
# UGLY: busy waiting for redis to become live.
while db.ping() != 'PONG':
  logger.info(db.ping())
  time.sleep(1)

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


def register_this_container():
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


def update_resources_for_this_host():
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


@app.route('/')
def top_level_handler():
  # Get request input
  json_data = request.get_json()

  # Work out which function this refers to
  func_name = json_data.get("func")

  # Execute the function who's name is provided
  value = execute_function(func_name)

  if value == 404:
    return "Error!", 404
  else:
    return value


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


def find_best_container_for_func(func_name, reqs):
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


def execute_function_on_host(best_host, func_name):
  """
  Executes the function on another host
  """
  r = requests.get("{best_host}", json={"func": func_name})
  return r.content


def execute_function(func_name):
  """
  Executes the function on this host
  """
  try:
    return getattr(functions, func_name)()
  except:
    return 404


def request_more_resources():
  """
  Asks knative for more application resources, because we think we've run out
  """
  logger.info("NEED MORE RESOURCES!!!!")

# --------------------------------------
# MAIN
# -------------------------------------


in_container = os.environ.get('IN_CONTAINER', False)
if (in_container):
  register_this_container()

if __name__ == "__main__":
  app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
