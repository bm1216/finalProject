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
import pickle
import torch
import network

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
pickled_db = redis.Redis(host=os.environ.get('REDIS_HOST', 'localhost'), decode_responses=False)



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

        if have_enough:
          # Execute the function and return
          # Get the serverless data. When to load?
          data_keys = resources.get("data")
          if (data_keys):
            for key in data_keys:
              if key == "state_dict":
                system.load_serverless_data(cache, pickled_db, key)
              else:
                system.load_serverless_data(cache, db, key)
          value = func(*args, **kwargs)
        else:
          # Find a better container
          best_host = system.find_best_container_for_func(cache, db, resources)

          if best_host:
            # We've found a better host, execute it there
            value = system.execute_function_on_host(best_host, args[0])
          else:
            if (data_keys):
              for key in data_keys:
                if key == "state_dict":
                  system.load_serverless_data(cache, pickled_db, key)
                else:
                  system.load_serverless_data(cache, db, key)

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



def execute_function(func_name, num):
  """
  Executes the function on this host
  """
  try:
    return globals()[func_name](func_name, num)
  except Exception as e:
    return e

def Fibonacci(n):
  if n<0: 
    logger.error("Incorrect input")
    return 0 
  # First Fibonacci number is 0 
  elif n==0: 
    return 0
  # Second Fibonacci number is 1 
  elif n==1: 
    return 1
  else: 
    return Fibonacci(n-1) + Fibonacci(n-2) 

def evaluate(rnn, line_tensor):
    hidden = rnn.initHidden()

    for i in range(line_tensor.size()[0]):
        output, hidden = rnn(line_tensor[i], hidden)

    return output

# all_letters = string.ascii_letters + " .,;'"
# n_letters = len(all_letters)
# # Find letter index from all_letters, e.g. "a" = 0
# def letterToIndex(letter):
#     return all_letters.find(letter)

# # Just for demonstration, turn a letter into a <1 x n_letters> Tensor
# def letterToTensor(letter):
#     tensor = torch.zeros(1, n_letters)
#     tensor[0][letterToIndex(letter)] = 1
#     return tensor

# # Turn a line into a <line_length x 1 x n_letters>,
# # or an array of one-hot letter vectors
# def lineToTensor(line):
#     tensor = torch.zeros(len(line), 1, n_letters)
#     for li, letter in enumerate(line):
#         tensor[li][0][letterToIndex(letter)] = 1
#     return tensor

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

@utils.timer
@req({"mem": "400MB", "cpu": "1.0"})
def function_four(*args, **kwargs):
  num = args[1]
  logger.info(num)
  return "{}".format(Fibonacci(num))

@utils.timer
@req({"mem": "600MB", "cpu": "0.8", "data": ["state_dict"]})
def function_five(*args, **kwargs):
  input_line = args[1]
  print(input_line)
  data = cache["state_dict"]
  state_dict = pickle.loads(data)
  rnn = network.RNN(57, 128, 18)
  rnn.load_state_dict(state_dict)
  rnn.eval()
  with torch.no_grad():
      output = evaluate(rnn, network.lineToTensor(input_line))
  logger.info(output)
  return "OK"

@utils.timer
@req({"mem": "500MB", "cpu": "0.8", "data": ["big_file"]})
def function_six(*args, **kwargs):
  data = cache["big_file"]
  return "{}".format(sys.getsizeof(data))
  

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
    value = execute_function(func_name, json_data.get("n"))
  except Exception as e:
    return e, 404

  return value


if __name__ == "__main__":
  app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
