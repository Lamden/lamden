import redis

'''
    State memory is the current state of the network without the entire blockchain history. This is useful for delegates
    who are taking care of things such as 
'''

class StateMemory(object):
    def __init__(self, host='localhost', port=1111):
        self.r = redis.StrictRedis(host=host, port=port, db=0)

    def get_balance(self, key):
        return self.r.hget('balances', key)

    def set_balance(self, key, value):
        return self.r.hset('balances', key, value)

    def get_stamps(self, key):
        return self.r.hget('balances', key)

    def set_stamps(self, key, value):
        # sanity check here tho
        return self.r.hset('balances', key, value)