from cilantro.transactions import TestNetTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
from cilantro.interpreters.utils import RedisSerializer as rs
from cilantro.interpreters.constants import *
import redis


'''
    A moronically simple testnet transaction to Redis query system to demonstrate how Seneca will ultimately work

    To do:
    Add to balance, subtract from another
    Vote for candidates
    Add stamps
    Remove stamps
'''

class TestNetInterpreter(object):
    def __init__(self, host='localhost', port=6379, db=0):
        self.r = redis.StrictRedis(host=host, port=port, db=db)

    def query_for_transaction(self, tx: TestNetTransaction):
        # 1. make sure the tx is signed by the right person
        full_tx = tx.payload['payload']
        assert TestNetTransaction.verify_tx(transaction=tx.payload,
                                            verifying_key=full_tx[1],
                                            signature=tx.payload['metadata']['signature'],
                                            wallet=ED25519Wallet,
                                            proof_system=SHA3POW)[0] \
            is True

        if full_tx[0] == TestNetTransaction.TX:
            query = self.query_for_std_tx(full_tx)
        elif full_tx[0] == TestNetTransaction.VOTE:
            pass
        elif full_tx[0] == TestNetTransaction.STAMP:
            pass
        else:
            pass

    def query_for_std_tx(self, transaction_payload: tuple):
        sender = transaction_payload[1]
        recipient = transaction_payload[2]
        amount = transaction_payload[3]

        sender_balance = rs.int(self.r.hget('balances', sender))
        assert sender_balance >= int(amount), 'Sender does not enough funds to send.'

        recipient_balance = rs.int(self.r.hget('balances', recipient))

        query = [
            (HSET, BALANCES, sender, sender_balance-int(amount)),
            (HSET, BALANCES, recipient, recipient_balance+int(amount))
        ]
        return query