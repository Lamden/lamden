from cilantro.transactions import TestNetTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
import redis

'''
    A moronically simple testnet transaction to Redis query system to demonstrate how Seneca will ultimately work
'''

class TestNetInterpreter(object):
    def __init__(self):
        # where the redis object gets initialized and connected
        pass

    @staticmethod
    def query_for_transaction(tx: TestNetTransaction):
        # 1. make sure the tx is signed by the right person
        full_tx = tx.payload['payload']
        print(TestNetTransaction.verify_tx(tx.payload, full_tx[1], tx.payload['metadata']['signature'], ED25519Wallet, SHA3POW))

'''
    To do:
    Add to balance, subtract from another
    Vote for candidates
    Add stamps
    Remove stamps
'''

(s, v) = ED25519Wallet.new()
tx = TestNetTransaction(ED25519Wallet, SHA3POW)
tx.build(TestNetTransaction.standard_tx(v, 'jason', '100'), s, use_stamp=False, complete=True)

TestNetInterpreter.query_for_transaction(tx)