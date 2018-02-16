import json
import redis
from cilantro.networking.delegate import Delegate
from cilantro.db.constants import *
import json
from cilantro.wallets.ed25519 import ED25519Wallet

def encode_tx(tx):
    return json.dumps(tx).encode()

def flush_scratch(r):
    print('flushing scratch...')
    for key in r.hscan_iter(SCRATCH_KEY):
        r.hdel(SCRATCH_KEY, key[0])

def flush_queue(r):
    print('flushing queue...')
    queue_len = r.llen(QUEUE_KEY)
    for _ in range(queue_len):
        r.lpop(QUEUE_KEY)

def flush_transactions(r):
    print('flushing transactions...')
    for key in r.hscan_iter(TRANSACTION_KEY):
        r.hdel(TRANSACTION_KEY, key[0])

def print_status(r):
    print('-----------------------------------')
    print('BALANCES')
    print(r.hgetall(BALANCE_KEY))
    print('-----------------------------------')
    print('SCRATCH')
    print(r.hgetall(SCRATCH_KEY))
    print('-----------------------------------')
    print('TRANSACTIONS')
    print(r.hgetall(TRANSACTION_KEY))
    print('-----------------------------------')
    print('QUEUE')
    queue_len = r.llen(QUEUE_KEY)
    for x in r.lrange(QUEUE_KEY, 0, queue_len):
        print(x)
    print('-----------------------------------\n')

def create_std_tx(sender: tuple, recipient: tuple, amount: float):
    """
    Utility method to create signed transaction
    :param sender: A tuple containing the (signing_key, verifying_key) of the sender
    :param recipient: A tuple containing the (signing_key, verifying_key) of the recipient
    :param amount: The amount to send
    :return:
    """
    tx = {'payload': {'to': recipient[1], 'amount': str(amount), 'from': sender[1], 'type':'t'}, 'metadata':
         {'sig':'???', 'proof': '000'}}
    tx['metadata']['signature'] = ED25519Wallet.sign(sender[0], json.dumps(tx['payload']).encode())
    return tx


STU = ('373ac0ec93038e4235c4716183afe55dab95f5d780415f60e7dd5363a2d2fd10',
       '403619540f4dfadc2da892c8d37bf243cd8d5a8e6665bc615f6112f0c93a3b09')
DAVIS = ('1f4be9265694ec059e11299ab9a5edce314f28accab38e09d770af36b1edaa27',
         '6fbc02647179786c10703f7fb82e625c05ede8787f5eeff84c5d9be03ff59ce8')
DENTON = ('c139bb396b4f7aa0bea43098a52bd89e411ef31dccd1497f4d27da5f63c53b49',
          'a86f22eabd53ea84b04e643361bd59b3c7b721b474b986ab29be10af6bcc0af1')

NEW_GUY = ('31935ede01db774f539133aa5a7017c734338e4c2d3d580f36fedf9921222abe',
           'a7bb55132f737c953ae6f8d159648815df1145fd0bf5c88ee757a096c19f4f6b')

r = redis.StrictRedis(host='localhost', port=6379, db=0)
d = Delegate()
trans = []

# Reset the Redis DBE
flush_queue(r)
flush_scratch(r)
flush_transactions(r)

trans.append(create_std_tx(STU, DAVIS, 125))
trans.append(create_std_tx(DAVIS, DENTON, 350))
trans.append(create_std_tx(DENTON, STU, 420))

# Add a transaction to a new user (user who is not yet in the current balance state)
trans.append(create_std_tx(STU, NEW_GUY, 1000))

# Execute the transactions and inspect the Redis DB
print_status(r)
for t in trans:
    d.process_transaction(data=encode_tx(t))
    print_status(r)






