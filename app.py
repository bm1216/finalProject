import os
from flask import Flask, request
​
# Adapted from the hello world Python found at
# https://knative.dev/docs/serving/samples/hello-world/helloworld-python/
​
app = Flask(__name__)
​
​
# -------------------------------------
# UNDERLYING SYSTEM
# -------------------------------------
​
def register_this_container():
    """
    Registers this container in the shared database. This allows other
    containers to look it up and send functions to it
    """
    pass
​
​
def update_resources_for_this_host():
    """
    Registers this container's resources in the shared database.
    """
    pass
​
​
@app.route('/')
def top_level_handler():
    # Get request input
    json_data = request.get_json()
​
    # Work out which function this refers to
    func_name = json_data.get("func")
​
    # Look up the resource requirements of this function based on the annotations
    reqs = look_up_func_requirements(func_name)
​
    # Do I have enough resources to execute this function?
    have_enough = check_resources(reqs)
​
    if have_enough:
        # Execute the function and return
        execute_function(func_name)
    else:
        # Find a better container
        best_host = find_best_container_for_func(func_name, reqs)
​
        if best_host:
            # We've found a better host, execute it there
            execute_function_on_host(best_host, func_name)
        else:
            # Have to execute it here as there's no better host
            execute_function(func_name)
            
            # This means the system is overloaded, we can request more resources from Knative?
            request_more_resources()
​
    # Update the records for this host
    update_resources_for_this_host()
​
​
def look_up_func_requirements(func_name):
    """
    Returns a JSON dictionary of the function's resource requirements
    """
    pass
​
​
def check_resources(reqs):
    """
    Checks if this host has enough resources
    """
    pass
​
​
def find_best_container_for_func(func_name, reqs):
    """
    Find the best container to execute this function
    """
    pass
​
​
def execute_function_on_host(best_host, func_name):
    """
    Executes the function on another host
    """
    pass
​
​
def execute_function(func_name):
    """
    Executes the function on this host
    """
    pass
​
​
def request_more_resources():
    """
    Asks knative for more application resources, because we think we've run out
    """
    pass
​
​
# -------------------------------------
# APPLICATION FUNCTIONS
# -------------------------------------
​
@func(mem="250MB", cpu="0.8")
def function_one():
    # TODO
    pass
​
​
@func(mem="500MB", cpu="0.5")
def function_two():
    # TODO
    pass
​
​
# --------------------------------------
# MAIN
# --------------------------------------
​
if __name__ == "__main__":
    register_this_container()
​
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))