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

from logger import logger
import system

# Adapted from the hello world Python found at
# https://knative.dev/docs/serving/samples/hello-world/helloworld-python/

app = Flask(__name__)

db = redis.Redis(host=os.environ.get('REDIS_HOST', 'redis'))
# UGLY: busy waiting for redis to become live.
while not db.ping():
  logger.info(db.ping())
  time.sleep(1)
  
# We need to execute this once initially or it returns 0.0
psutil.cpu_percent(percpu=True, interval=None)

def req(resources):
  def decorator_resource(func):
    @functools.wraps(func)
    def wrapper_resource(*args, **kwargs):
      # Do I have enough resources to execute this function?
      have_enough = system.check_resources(resources)

      logger.info("HAVE ENOUGH: " + str(have_enough))

      if have_enough:
        # Execute the function and return
        value = func(*args, **kwargs)
      else:
        # Find a better container
        best_host = system.find_best_container_for_func(db, args[0], resources)

        if best_host:
          # We've found a better host, execute it there
          value = system.execute_function_on_host(best_host, args[0])
        else:
          # Have to execute it here as there's no better host
          value = func(*args, **kwargs)

          # This means the system is overloaded, we can request more resources from Knative?
          system.request_more_resources()

      # Update the records for this host
      system.update_resources_for_this_host(db)
      return value

    return wrapper_resource
  return decorator_resource


def execute_function(func_name):
  """
  Executes the function on this host
  """
  try:
    return globals()[func_name](func_name)
  except:
    return 404

# -------------------------------------
# APPLICATION FUNCTIONS
# -------------------------------------

@req({"mem": "250MB", "cpu": "0.8"})
def function_one(*args, **kwargs):
  # TODO
  return "Hello function one."


@req({"mem": "500MB", "cpu": "0.5"})
def function_two(*args, **kwargs):
  # TODO
  return "Hello function two."

# --------------------------------------
# MAIN
# -------------------------------------

in_container = os.environ.get('IN_CONTAINER', False)
if (in_container):
  system.register_this_container(db)

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


if __name__ == "__main__":
  app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
