FROM redis

# Put config in place
COPY deploy/conf/redis.conf /redis.conf

CMD ["redis-server", "/redis.conf"]