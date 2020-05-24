from annotations import req

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