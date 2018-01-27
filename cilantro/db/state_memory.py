import redis

class StateMemory(object):
    def __init__(self, host='localhost', port=1111):
        self.r = redis.StrictRedis(host=host, port=port, db=0)

    def get_balance(self, key):
        pass

    def get_stamps(self, key):
        pass

    def set_stamps(self, key):
        pass