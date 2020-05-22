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

import psutil

# Adapted from the hello world Python found at
# https://knative.dev/docs/serving/samples/hello-world/helloworld-python/

app = Flask(__name__)
db = redis.Redis(host=os.environ.get('REDIS_HOST', 'redis'))
ONE_MB = 1024.0 * 1024.0

# -------------------------------------
# UNDERLYING SYSTEM
# -------------------------------------


def register_this_container():
  """
  Registers this container in the shared database. This allows other
  containers to look it up and send functions to it
  """

  # Get container id. 
  bashCommand = """head -1 /proc/self/cgroup|cut -d/ -f3"""
  output = subprocess.check_output(['bash','-c', bashCommand])

  db.rpush("containers", output)


def update_resources_for_this_host():
  """
  Registers this container's resources in the shared database.
  """
  pass


@app.route('/')
def top_level_handler():
  # Get request input
  json_data = request.get_json()

  ## Work out which function this refers to
  func_name = json_data.get("func")

  # Execute the function who's name is provided
  value = execute_function(func_name)

  if value == 404:
    return "Error!", 404
  else:
    return value



def check_resources(reqs):
  """
  Checks if this host has enough resources
  """

  # We need to execute this once initially or it returns 0.0
  psutil.cpu_percent(percpu=True, interval=None)

  cpu_pct_per_cpu = psutil.cpu_percent(percpu=True)
  mem = psutil.virtual_memory()
  req_mem = float(''.join(filter(str.isdigit, reqs.mem)))
  
  # Check if both memory and cpu constraints are satisfied.
  if (mem.available/ONE_MB > req_mem):
    for util in cpu_pct_per_cpu:
      free = (100 - util)/100
      if ( free > reqs.cpu ):
        return True
    return False
  else:
    return False


def find_best_container_for_func(func_name, reqs):
  """
  Find the best container to execute this function
  """
  pass


def execute_function_on_host(best_host, func_name):
  """
  Executes the function on another host
  """
  pass


def execute_function(func_name):
  """
  Executes the function on this host
  """
  try:
    return globals()[func_name]()
  except:
    return 404



def request_more_resources():
  """
  Asks knative for more application resources, because we think we've run out
  """
  pass

def req(resources):
  def decorator_resource(func):
    @functools.wraps(func)
    def wrapper_resource(*args, **kwargs):
      # # Do I have enough resources to execute this function?
      have_enough = check_resources(resources)

      if have_enough:
        # Execute the function and return
        value = func(*args, **kwargs)
        return value
      # else:
      #     # Find a better container
      #     best_host = find_best_container_for_func(func_name, reqs)

      #     if best_host:
      #         # We've found a better host, execute it there
      #         execute_function_on_host(best_host, func_name)
      #     else:
      #         # Have to execute it here as there's no better host
      #         execute_function(func_name)

      #         # This means the system is overloaded, we can request more resources from Knative?
      #         request_more_resources()

      # Update the records for this host
      update_resources_for_this_host()

    return wrapper_resource
  return decorator_resource

# -------------------------------------
# APPLICATION FUNCTIONS
# -------------------------------------

@req({"mem": "250MB", "cpu": "0.8"})
def function_one():
  # TODO
  return "Hello function one."

@req({"mem": "500MB", "cpu": "0.5"})
def function_two():
  # TODO
  return "Hello function two."

# --------------------------------------
# MAIN
# -------------------------------------


if __name__ == "__main__":
  register_this_container()
  app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
