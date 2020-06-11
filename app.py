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
import sys
import psutil
import signal
import threading
import utils
import random

from logger import logger
import system

# Adapted from the hello world Python found at
# https://knative.dev/docs/serving/samples/hello-world/helloworld-python/

app = Flask(__name__)
cache = {}
use_scheduler = os.environ.get('USE_SCHEDULER') == "True"

# We need to execute this once initially or it returns 0.0
psutil.cpu_percent(percpu=True, interval=None)

db = redis.Redis(host=os.environ.get('REDIS_HOST', 'localhost'), decode_responses=True)

# UGLY: busy waiting for redis to become live.
while not db.ping():
  logger.info(db.ping())
  time.sleep(1)

system.register_this_container(cache, db)
# Handler for exit signal
def exit_gracefully(signum, frame):
  logger.info("Quitting Gracefully. Removing containers from db.")
  db.srem("containers", cache["ip"])
  db.delete(cache["ip"])
  sys.exit()

signal.signal(signal.SIGINT, exit_gracefully)
signal.signal(signal.SIGTERM, exit_gracefully)

def thread_function():
  """
    Gets and updates resource usage in the background.
  """
  while True:    
    free_cpu, free_mem = system.get_resources()
    my_ip = cache["ip"]

    logger.info("UPDATING", extra = {"cpu": free_cpu, "mem": free_mem, "ip": my_ip})
    db.hset(my_ip, mapping={"cpu": free_cpu, "mem": free_mem})
    time.sleep(8)
  
update = threading.Thread(target=thread_function, daemon=True)
update.start()

def req(resources):
  def decorator_resource(func):
    @functools.wraps(func)
    def wrapper_resource(*args, **kwargs):
      # Do I have enough resources to execute this function?
      if use_scheduler:
        have_enough = system.check_resources(resources)

        logger.info("HAVE ENOUGH: " + str(have_enough))

        # Get the serverless data. When to load?
        data_keys = resources.get("data")
        if (data_keys):
          for key in data_keys:
            system.load_serverless_data(cache, db, key)

        if have_enough:
          # Execute the function and return
          value = func(*args, **kwargs)
        else:
          # Find a better container
          best_host = system.find_best_container_for_func(cache, db, resources)

          if best_host:
            # We've found a better host, execute it there
            value = system.execute_function_on_host(best_host, args[0])
          else:
            # Have to execute it here as there's no better host
            value = func(*args, **kwargs)

            # This means the system is overloaded, we can request more resources from Knative?
            system.request_more_resources()
      else:
        logger.info("NO SCHEDULING INVOLVED")
        value = func(*args, **kwargs)

      # Update the records for this host
      # system.update_resources_for_this_host(cache, db)
      return value

    return wrapper_resource
  return decorator_resource



def execute_function(func_name):
  """
  Executes the function on this host
  """
  try:
    return globals()[func_name](func_name)
  except Exception as e:
    return e

# -------------------------------------
# APPLICATION FUNCTIONS
# -------------------------------------

@utils.timer
@req({"mem": "250MB", "cpu": "0.8", "data": ["model1"]})
def function_one(*args, **kwargs):
  # TODO
  data = cache["model1"]
  return "The cache exists in the API = " + data 

@utils.timer
@req({"mem": "500MB", "cpu": "0.5"})
def function_two(*args, **kwargs):
  # TODO
  # my_name = "Barun Mishra"
  # Who stores the data? When is it stored?
  return cache["ip"] 

@req({"mem": "400MB", "cpu": "0.4", "data": ["model2"]})
def function_three(*args, **kwargs):
  r = random.randrange(30)
  time.sleep(r)

  return "SLEPT FOR {} seconds. The data is {}".format(r, cache["model2"])

# --------------------------------------
# MAIN
# -------------------------------------

@app.route('/')
def top_level_handler():
  # Get request input
  json_data = request.get_json()

  # Work out which function this refers to
  func_name = json_data.get("func")

  # Execute the function who's name is provided
  try:
    value = execute_function(func_name)
  except Exception as e:
    return e, 404

  return value


if __name__ == "__main__":
  app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
