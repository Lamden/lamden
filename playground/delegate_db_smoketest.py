import json
import redis
from cilantro.networking.delegate import Delegate
from cilantro.db.constants import *

def encode_tx(tx):
    return json.dumps(tx).encode()

t1 = {'payload': {'to': 'davis', 'amount': '100', 'from': 'stu', 'type':'t'}, 'metadata': {'sig':'x287', 'proof': '000'}}

d = Delegate()
d.process_transaction(data=encode_tx(t1))

r = redis.StrictRedis(host='localhost', port=6379, db=0)
queue_len = r.llen(QUEUE_KEY)

print('\n-----------------------------------')
print('BALANCES')
print(r.hgetall(BALANCE_KEY))

print('\n-----------------------------------')
print('SCRATCH')
print(r.hgetall(SCRATCH_KEY))

print('\n-----------------------------------')
print('QUEUE')
for x in r.lrange(QUEUE_KEY, 0, queue_len):
    print(x)
