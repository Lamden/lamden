from cilantro.transactions import TestNetTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
import redis

'''
    A moronically simple testnet transaction to Redis query system to demonstrate how Seneca will ultimately work
'''

class TestNetInterpreter(object):
    @staticmethod
    def query_for_transaction(tx: dict):
        # 1. make sure the tx is signed by the right person
        full_tx = tx['payload']
        assert TestNetTransaction.verify_tx(full_tx, full_tx[1], )
        type = full_tx[0]
        print(full_tx)


(s, v) = ED25519Wallet.new()
TO = 'jason'
AMOUNT = '1001'

tx = TestNetTransaction.standard_tx(v, TO, AMOUNT)

transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=SHA3POW)
transaction_factory.build(tx, s, complete=True, use_stamp=True)

full_tx = transaction_factory.payload
sig = full_tx['metadata']['signature']

TestNetInterpreter.query_for_transaction(full_tx)