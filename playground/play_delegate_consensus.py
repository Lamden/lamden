# Redis for state changes but also for the 'proposed' state changes
# ID each tx or put them on a set?

'''

FIFO queue
SSET pending_tx
where is a data blob?
where it's the series of state changes?

'''

from cilantro.transactions import TestNetTransaction
from cilantro.proofs.pow import POW
from cilantro.interpreters import TestNetInterpreter
from cilantro.wallets import ED25519Wallet

from pprint import pprint
'''

    Steps:
    1. create a ton of wallets
    2. create a ton of random transactions for those wallets
    3. interpret those transactions and verify them
    4. put the db output stack in a list
    5. figure it out from there.

'''
import random

NUM_WALLETS = 100
wallets = [ED25519Wallet.new() for x in range(NUM_WALLETS)]

transactions = []

setup_queries = []

interpreter = TestNetInterpreter()

def generate_random_std_transaction():
    from_wallet, to_wallet = random.sample(wallets, 2)
    amount = str(random.randint(1, 1000))

    tx = TestNetTransaction.standard_tx(from_wallet[0], to_wallet[0], amount)

    transaction_builder = TestNetTransaction(ED25519Wallet, POW)
    transaction_builder.build(tx, from_wallet[1], complete=True, use_stamp=False)

    setup_queries.append('add {} to balances {}'.format(amount, from_wallet[0]))

    transactions.append(transaction_builder)

def generate_random_stamp_transaction():
    from_wallet = random.choice(wallets)
    amount = str(random.randint(-1000, 1000))

    tx = TestNetTransaction.stamp_tx(from_wallet[0], amount)

    transaction_builder = TestNetTransaction(ED25519Wallet, POW)
    transaction_builder.build(tx, from_wallet[1], complete=True, use_stamp=False)

    location = 'balance'
    if int(amount) < 0:
        location = 'stamp'
        amount = str(int(amount)*-1)

    setup_queries.append('add {} to {} {}'.format(amount, location, from_wallet[0]))
    transactions.append(transaction_builder)

def generate_random_vote_transaction():
    pass

for i in range(100):
    generate_random_stamp_transaction()

print(setup_queries)