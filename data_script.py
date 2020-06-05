import redis
import os


db = redis.Redis(os.environ.get('REDIS_HOST', 'localhost'))


model1 = '{"epochs": 50, "alpha": 0.001, "batch_size": 32}'
model2 = '{"epochs": 25, "alpha": 0.1, "batch_size": 128}'


db.set("model1", model1)
db.set("model2", model2)


