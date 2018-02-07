from cilantro.transactions import TestNetTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
from cilantro.interpreters.utils import RedisSerializer as rs
from cilantro.interpreters.constants import *
import redis
import hashlib

'''
    A moronically simple testnet transaction to Redis query system to demonstrate how Seneca will ultimately work

    To do:
    Add to balance, subtract from another
    Vote for candidates
    Add stamps
    Remove stamps
'''


class TestNetInterpreter(object):
    def __init__(self, host='localhost', port=6379, db=0, wallet=ED25519Wallet, proof_system=SHA3POW) :
        self.r = redis.StrictRedis(host=host, port=port, db=db)
        self.wallet = wallet
        self.proof_system = proof_system

    def query_for_transaction(self, tx: TestNetTransaction):
        # 1. make sure the tx is signed by the right person
        full_tx = tx.payload['payload']

        assert TestNetTransaction.verify_tx(transaction=tx.payload,
                                            verifying_key=full_tx[1],
                                            signature=tx.payload['metadata']['signature'],
                                            wallet=self.wallet,
                                            proof_system=self.proof_system)[0] \
            is True

        # assume failure, prove otherwise
        query = FAIL
        if full_tx[0] == TestNetTransaction.TX:
            query = self.query_for_std_tx(full_tx)
        elif full_tx[0] == TestNetTransaction.VOTE:
            query = self.query_for_vote_tx(full_tx)
        elif full_tx[0] == TestNetTransaction.STAMP:
            query = self.query_for_stamp_tx(full_tx)
        elif full_tx[0] == TestNetTransaction.SWAP:
            query = self.query_for_swap_tx(full_tx)
        else:
            pass

        return query

    def query_for_std_tx(self, transaction_payload: tuple):
        sender = transaction_payload[1]
        recipient = transaction_payload[2]
        amount = transaction_payload[3]

        sender_balance = rs.int(self.r.hget(BALANCES, sender))
        assert sender_balance >= int(amount), 'Sender does not enough funds to send. Has {} needs {}.'.format(sender_balance, int(amount))

        recipient_balance = rs.int(self.r.hget(BALANCES, recipient))

        query = [
            (HSET, BALANCES, sender, sender_balance-int(amount)),
            (HSET, BALANCES, recipient, recipient_balance+int(amount))
        ]
        return query

    def query_for_vote_tx(self, transaction_payload: tuple):
        sender = transaction_payload[1]
        candidate = transaction_payload[2]

        query = [
            (HSET, VOTES, sender, candidate)
        ]
        return query

    def query_for_stamp_tx(self, transaction_payload: tuple):
        sender = transaction_payload[1]
        amount = transaction_payload[2]

        if int(amount) > 0:
            sender_balance = rs.int(self.r.hget(BALANCES, sender))
            assert sender_balance >= int(amount), 'Sender does not enough funds to send.'

            sender_stamps = rs.int(self.r.hget(STAMPS, sender))

            query = [
                (HSET, BALANCES, sender, sender_balance - int(amount)),
                (HSET, STAMPS, sender, sender_stamps + int(amount))
            ]

        else:
            sender_stamps = rs.int(self.r.hget(STAMPS, sender))
            assert sender_stamps >= int(amount), 'Sender does not enough stamps to send.'

            sender_balance = rs.int(self.r.hget(BALANCES, sender))

            query = [
                (HSET, STAMPS, sender, sender_stamps + int(amount)),
                (HSET, BALANCES, sender, sender_balance - int(amount))
            ]

        return query

    def query_for_swap_tx(self, tx):
        sender, recipient, amount, hash_lock, unix_expiration = tx[1:]

        if self.r.hgetall(hash_lock) is None:
            return [(HMSET, hash_lock, sender, recipient, amount, unix_expiration)]
        else:
            return FAIL

    def query_for_redeem_tx(self, tx):
        secret = bytes.fromhex(tx[1])

        ripe = hashlib.new('ripemd160')
        ripe.update(secret)
        hash_lock = ripe.digest().hex()

        q = self.r.hgetall(hash_lock)
        if q is None:
            return FAIL
        else:
            pass
            # transfer funds