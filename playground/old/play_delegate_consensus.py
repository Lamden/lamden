# Redis for state changes but also for the 'proposed' state changes
# ID each tx or put them on a set?

'''
    FIFO queue
    SSET pending_tx
    where is a data blob?
    where it's the series of state changes?
'''

from cilantro.protocol.transactions import TestNetTransaction
from cilantro.protocol.proofs import POW
from cilantro.protocol.interpreters import TestNetInterpreter
from cilantro.protocol.wallet import Wallet

'''
    Steps:
    1. create a ton of wallets
    2. create a ton of random transaction for those wallets
    3. interpret those transaction and verify them
    4. put the db output stack in a list
    5. figure it out from there.
'''
import random
import redis

NUM_WALLETS = 100
wallets = [Wallet.new() for x in range(NUM_WALLETS)]

txs = []

interpreter = TestNetInterpreter(proof_system=POW)

setup_queries = {}

def generate_random_std_transaction():
    from_wallet, to_wallet = random.sample(wallets, 2)
    amount = str(random.randint(1, 1000))

    tx = TestNetTransaction.standard_tx(from_wallet[1], to_wallet[1], amount)

    transaction_builder = TestNetTransaction(Wallet, POW)
    transaction_builder.build(tx, from_wallet[0], complete=True, use_stamp=False)

    try:
        setup_queries[from_wallet[1]][BALANCES] += int(amount)
    except:
        setup_queries[from_wallet[1]] = {}
        setup_queries[from_wallet[1]][BALANCES] = int(amount)

    txs.append(transaction_builder)

def generate_random_stamp_transaction():
    from_wallet = random.choice(wallets)
    amount = str(random.randint(-1000, 1000))

    tx = TestNetTransaction.stamp_tx(from_wallet[1], amount)

    transaction_builder = TestNetTransaction(Wallet, POW)
    transaction_builder.build(tx, from_wallet[0], complete=True, use_stamp=False)

    location = BALANCES
    if int(amount) < 0:
        location = STAMPS
        amount = str(int(amount)*-1)

    try:
        setup_queries[from_wallet[1]][location] += int(amount)
    except:
        setup_queries[from_wallet[1]] = {}
        setup_queries[from_wallet[1]][location] = int(amount)

    txs.append(transaction_builder)


def generate_random_vote_transaction():
    from_wallet, to_wallet = random.sample(wallets, 2)

    tx = TestNetTransaction.vote_tx(from_wallet[1], to_wallet[1])

    transaction_builder = TestNetTransaction(Wallet, POW)
    transaction_builder.build(tx, from_wallet[0], complete=True, use_stamp=False)

    txs.append(transaction_builder)


for i in range(100):
    random.choice([
        generate_random_std_transaction(),
        #generate_random_stamp_transaction()
    ])

r = redis.StrictRedis(host='localhost', port=6379, db=0)

for q in setup_queries:
    for k in list(setup_queries[q].keys()):
        r.hset(k, q, setup_queries[q][k])

for t in txs:
    print(interpreter.query_for_transaction(t))

import hashlib
import pickle
h = hashlib.sha3_256()
h.update(pickle.dumps(txs))
print(h.digest().hex())
print(txs)

