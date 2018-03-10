import redis
from cilantro.logger import get_logger

class DriverBase(object):
    def __init__(self, host='localhost', port=6379, db=0):
        self.log = get_logger("DB-#{}".format(db))
        self.log.debug("Startup DB Driver with DB #{}".format(db))
        self.r = redis.StrictRedis(host=host, port=port, db=db)
