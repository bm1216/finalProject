import app
import functools

def req(resources):
  def decorator_resource(func):
    @functools.wraps(func)
    def wrapper_resource(*args, **kwargs):
      # Do I have enough resources to execute this function?
      have_enough = app.check_resources(resources)

      logger.info("HAVE ENOUGH: " + str(have_enough))

      if have_enough:
        # Execute the function and return
        value = func(*args, **kwargs)
      else:
        # Find a better container
        best_host = app.find_best_container_for_func(func_name, resources)

        if best_host:
          # We've found a better host, execute it there
          value = app.execute_function_on_host(best_host, func_name)
        else:
          # Have to execute it here as there's no better host
          value = func(*args, **kwargs)

          # This means the system is overloaded, we can request more resources from Knative?
          app.request_more_resources()

      # Update the records for this host
      app.update_resources_for_this_host()
      return value

    return wrapper_resource
  return decorator_resource