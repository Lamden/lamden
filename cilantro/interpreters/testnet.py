from cilantro.transactions import TestNetTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
from cilantro.interpreters.utils import RedisSerializer as rs
from cilantro.interpreters.constants import *
import redis
import hashlib

from cilantro.db.balance_db import BalanceDB
from cilantro.db.scratch_db import ScratchDB

'''
    A moronically simple testnet transaction to Redis query system to demonstrate how Seneca will ultimately work

    To do:
    Add to balance, subtract from another
    Vote for candidates
    Add stamps
    Remove stamps
'''


class TestNetInterpreter(object):

    def __init__(self, wallet=ED25519Wallet, proof_system=SHA3POW):
        self.balance = BalanceDB()
        self.scratch = ScratchDB()
        self.wallet = wallet
        self.proof_system = proof_system

    def interpret_transaction(self, transaction: TestNetTransaction):
        """
        Interprets the transaction, and updates scratch/balance state as necessary.
        If any validation fails (i.e. insufficient balance), this method will throw an error

        :param transaction: A TestNetTransaction object to interpret
        """
        INTERPRETER_MAP = {TestNetTransaction.TX: self.interpret_std_tx,
                           TestNetTransaction.VOTE: self.interpret_vote_tx,
                           TestNetTransaction.STAMP: self.interpret_stamp_tx,
                           TestNetTransaction.SWAP: self.interpret_stamp_tx,
                           TestNetTransaction.REDEEM: self.interpret_redeem_tx}

        tx_payload = transaction.payload

        # TODO -- support functionality below
        # if not TestNetTransaction.verify_tx(transaction=tx_payload, verifying_key=tx_payload[1],
        #                                     signature=tx_payload['metadata']['signature'], wallet=self.wallet,
        #                                     proof_system=self.proof_system)[0]:
        #     raise Exception("Interpreter could not verify transaction")

        INTERPRETER_MAP[tx_payload[0]](tx_payload)

    def interpret_std_tx(self, transaction: TestNetTransaction):

        print('(in interpret std tx) transaction payload: {}'.format(transaction))

        sender = transaction[1]
        recipient = transaction[2]
        amount = int(transaction[3])

        # check if it is in scratch
        if self.scratch.wallet_exists(sender):
            # Is tx valid against scratch?
            scratch_balance = self.scratch.get_balance(sender)
            if scratch_balance - amount >= 0:
                # Update scratch
                self.scratch.set_balance(sender, scratch_balance - amount)
            else:
                raise Exception("Error: sender does not have enough balance (against scratch)")
        else:
            # Is tx valid against main db?
            balance = self.balance.get_balance(sender)
            if balance >= amount:
                # Update scratch
                self.scratch.set_balance(sender, balance - amount)
            else:
                raise Exception("Error: sender does not have enough balance (against main balance)")

    def interpret_vote_tx(self, transaction: TestNetTransaction):
        raise NotImplementedError

    def interpret_stamp_tx(self, transaction: TestNetTransaction):
        raise NotImplementedError

    def interpret_swap_tx(self, transaction: TestNetTransaction):
        raise NotImplementedError

    def interpret_redeem_tx(self, transaction: TestNetTransaction):
        raise NotImplementedError

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

        # assert that the sender can 'stake' for the atomic swap
        sender_balance = rs.int(self.r.hget(BALANCES, sender))
        if sender_balance < int(amount):
            return FAIL

        if len(self.r.hgetall(hash_lock)) == 0:
            return [
                (HSET, BALANCES, sender, sender_balance - int(amount)),
                (HMSET, SWAP, hash_lock, sender, recipient, amount, unix_expiration)
            ]
        else:
            return FAIL

    def query_for_redeem_tx(self, tx, metadata):
        secret = bytes.fromhex(tx[1])

        ripe = hashlib.new('ripemd160')
        ripe.update(secret)
        hash_lock = ripe.digest().hex()

        q = self.r.hgetall(hash_lock)

        if len(q) == 0:
            return FAIL
        else:
            # assert sender is the true sender
            sig = metadata['signature']
            msg = None
            d = rs.dict(q)
            if self.wallet.verify(d['recipient'], msg, sig) is True:
                # transfer funds
                # get the recipient's balance
                recipient_balance = self.r.hget(BALANCES, d['recipient'])
                return [
                    (HSET, BALANCES, d['recipient'], rs.int(recipient_balance) + int(d['amount'])),
                    (DEL, hash_lock)
                ]
            else:
                return FAIL
