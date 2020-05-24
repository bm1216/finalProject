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

from datetime import datetime

# Adapted from the hello world Python found at
# https://knative.dev/docs/serving/samples/hello-world/helloworld-python/

app = Flask(__name__)

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

import system 


db = redis.Redis(host=os.environ.get('REDIS_HOST', 'redis'))
# UGLY: busy waiting for redis to become live.
while db.ping() != 'PONG':
  logger.info(db.ping())
  time.sleep(1)


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
      # else:
      #   # Find a better container
      #   best_host = system.find_best_container_for_func(db, func_name, resources)

      #   if best_host:
      #     # We've found a better host, execute it there
      #     value = system.execute_function_on_host(best_host, func_name)
      #   else:
      #     # Have to execute it here as there's no better host
      #     value = func(*args, **kwargs)

      #     # This means the system is overloaded, we can request more resources from Knative?
      #     system.request_more_resources()

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
    return globals()[func_name]()
  except:
    return 404

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
