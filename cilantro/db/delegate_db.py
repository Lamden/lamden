import redis

'''
    DelegateDB is the current state of the network without the entire blockchain history. This is useful for delegates
    who are taking care of things such as 
'''

class DelegateDB(object):
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

    def add_to_block(self, tx):
        # adds a tx payload to the set where the key is the previous blockhash
        pass

    def consume_transaction(self, tx):
        # takes a transactional payload and turns it into queries
        pass