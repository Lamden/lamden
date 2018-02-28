import redis
from cilantro.nodes.delegate import Delegate
from cilantro.utils.constants import *
import json
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.proofs import SHA3POW
from cilantro.protocol.serialization.json_serializer import JSONSerializer

r = redis.StrictRedis(host='localhost', port=6379, db=0)

def encode_tx(tx):
    return json.dumps(tx).encode()

def flush_scratch():
    print('flushing scratch...')
    for key in r.hscan_iter(SCRATCH_KEY):
        r.hdel(SCRATCH_KEY, key[0])

def flush_queue():
    print('flushing queue...')
    queue_len = r.llen(QUEUE_KEY)
    for _ in range(queue_len):
        r.lpop(QUEUE_KEY)

def flush_transactions():
    print('flushing transactions...')
    for key in r.hscan_iter(TRANSACTION_KEY):
        r.hdel(TRANSACTION_KEY, key[0])

def print_balance():
    for person, balance in r.hgetall(BALANCE_KEY).items():
        print("{} : {}".format(person, balance))

def print_scratch():
    for person, balance in r.hgetall(SCRATCH_KEY).items():
        print("{} : {}".format(person, balance))

def print_queue():
    queue_len = r.llen(QUEUE_KEY)
    for x in r.lrange(QUEUE_KEY, 0, queue_len):
        print(x)

def print_status():
    print('-----------------------------------')
    print('BALANCES')
    print_balance()
    print('-----------------------------------')
    print('SCRATCH')
    print_scratch()
    print('-----------------------------------')
    print('QUEUE')
    print_queue()
    print('-----------------------------------\n')

def create_std_tx(sender: tuple, recipient: tuple, amount: float):
    """
    Utility method to create signed transaction
    :param sender: A tuple containing the (signing_key, verifying_key) of the sender
    :param recipient: A tuple containing the (signing_key, verifying_key) of the recipient
    :param amount: The amount to send
    :return:
    """
    # TestNetTransaction.TX, sender, to, amount
    tx = {'payload': ('t', sender[1], recipient[1], str(amount)), 'metadata':{}}
    tx["metadata"]["proof"] = SHA3POW.find(JSONSerializer.serialize(tx["payload"]))[0]
    # tx["metadata"]["signature"] = ED25519Wallet.sign(sender[0], json.dumps(tx["payload"]).encode())
    tx["metadata"]["signature"] = ED25519Wallet.sign(sender[0], JSONSerializer.serialize(tx['payload']))
    return tx


STU = ('24e90019ce7dbfe3f6e8bada161540e1330d8d51bff7e524bcd34b7fbefb0d9a260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f',
 '260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f')
DAVIS = ('d851136c3a2e0b93c929b184f75644d923a6c372bac7de1dc8a5353d07433123f7947784333851ec363231ade84ca63b21d03e575b1919f4042959bcd3c89b5f',
 'f7947784333851ec363231ade84ca63b21d03e575b1919f4042959bcd3c89b5f')
DENTON = ('c139bb396b4f7aa0bea43098a52bd89e411ef31dccd1497f4d27da5f63c53b49',
          'a86f22eabd53ea84b04e643361bd59b3c7b721b474b986ab29be10af6bcc0af1')

NEW_GUY = ('31935ede01db774f539133aa5a7017c734338e4c2d3d580f36fedf9921222abe',
           'a7bb55132f737c953ae6f8d159648815df1145fd0bf5c88ee757a096c19f4f6b')

d = Delegate()
trans = []

# Reset the Redis DBE
flush_queue()
flush_scratch()
flush_transactions()

trans.append(create_std_tx(STU, DAVIS, 1))
trans.append(create_std_tx(DAVIS, STU, 1))
# trans.append(create_std_tx(DAVIS, DENTON, 1))
# trans.append(create_std_tx(DENTON, STU, 1))

# Add a transaction to a new user (user who is not yet in the current balance state)
# trans.append(create_std_tx(STU, NEW_GUY, 1000))

# Execute the transactions and inspect the Redis DB
print_status()
for t in trans:
    d.process_transaction(data=encode_tx(t))
    print_status()






