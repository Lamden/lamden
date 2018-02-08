import redis
from cilantro.interpreters.utils import RedisSerializer as rs

class BaseDB(object):
    def __init__(self, host='localhost', port=6379, db=0):
        self.r = redis.StrictRedis(host=host, port=port, db=db)
