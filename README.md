# finalProject

This is a distributed scheduler that loadbalances requests between serverless functions based on resource requirements and data dependencies specified.

## Function Definition

```python
@req({"mem": "500MB", "cpu": "0.5", "data": ["model1"]})
def function(*args, **kwargs):
  value = cache["model1"]
  epochs = value["epochs"]
  alpha = value["learning_rate"]
  batch_size = value["batch_size"]
 
  return "Hello World"
```

As can be seen from the case above, the memory should be defined in Megabytes and the CPU in percentage of virtual cores required. Data can also be provided where upon the scheduler will try to load it into a container that has the data in cache.
