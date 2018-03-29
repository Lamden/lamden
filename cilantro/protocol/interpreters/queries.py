from cilantro.messages.utils import int_to_decimal
from cilantro import Constants
from cilantro.utils import Encoder as E
import hashlib
import time
from cilantro.db.delegate.backend import *


class StateQuery:
    def __init__(self, table_name, backend):
        self.table_name = table_name
        self.backend = backend

        self.txq = TransactionQueue(backend=self.backend)

    def process_tx(self, tx: dict):
        raise NotImplementedError

    def __str__(self):
        return self.table_name


class StandardQuery(StateQuery):
    """
    StandardQuery
    Automates the state and txq modifications for standard transactions
    """
    def __init__(self, table_name=BALANCES, backend=SQLBackend()):
        super().__init__(table_name=table_name, backend=backend)

    def get_balance(self, address):
        self.backend.execute('use scratch;')
        q = 'select * from {} where wallet="{}";'.format(self.table_name, address)
        self.backend.execute(q)
        r = self.backend.db.fetchone()

        if r is None:
            self.backend.execute('use state;')
            q = 'select * from {} where wallet="{}";'.format(self.table_name, address)
            self.backend.execute(q)
            r = self.backend.db.fetchone()

        if r is None:
            return None

        return r[-1]

    def process_tx(self, tx):
        sender_balance = self.get_balance(tx.sender)

        if sender_balance >= tx.amount:

            receiver_balance = self.get_balance(tx.receiver)

            new_sender_balance = sender_balance - tx.amount

            new_receiver_balance = receiver_balance + tx.amount

            self.backend.replace(self.scratch_table, (tx.sender), (new_sender_balance))
            self.backend.replace(self.scratch_table, (tx.receiver), (new_receiver_balance))

            return tx, (self.scratch_table, tx.sender.encode(), new_sender_balance), \
                   (self.scratch_table, tx.receiver.encode(), new_receiver_balance)
        else:
            return None, None, None


class VoteQuery(StateQuery):
    """
    VoteQuery
    Automates the state modifications for vote transactions
    """
    def __init__(self, table_name=VOTES, backend=SQLBackend()):
        super().__init__(table_name=table_name, backend=backend)

    def process_tx(self, tx):
        try:
            k = tx.policy.encode() + SEPARATOR + tx.sender.encode()
            v = tx.choice.encode()
            self.backend.set(self.scratch_table, k, v)
            return tx, (self.scratch_table, k, v)
        except Exception as e:
            return None, None


class SwapQuery(StandardQuery):
    """
    SwapQuery
    Automates the state modifications for swap transactions
    """
    def __init__(self, table_name=SWAPS, backend=SQLBackend()):
        super().__init__(table_name=table_name, backend=backend)
        self.balance_table = BALANCES
        self.balance_scratch = SEPARATOR.join([SCRATCH, self.balance_table])

    @staticmethod
    def amount_key(address, hashlock):
        return address + SEPARATOR + hashlock + SEPARATOR + b'amount'

    @staticmethod
    def expiration_key(address, hashlock):
        return address + SEPARATOR + hashlock + SEPARATOR + b'expiration'

    def get_balance(self, address):
        table = self.balance_table
        if self.backend.exists(self.scratch_table, address.encode()):
            table = self.balance_scratch

        return self.balance_to_decimal(table, address)

    def process_tx(self, tx):
        sender_balance = self.get_balance(tx.sender)

        if sender_balance >= tx.amount:
            # subtract the balance from the sender
            new_sender_balance = sender_balance - tx.amount
            new_sender_balance = self.encode_balance(new_sender_balance)

            self.backend.set(self.balance_scratch, tx.sender.encode(), new_sender_balance)

            # place the balance into the swap
            amount_key = self.amount_key(tx.receiver.encode(), tx.hashlock)
            expiration_key = self.expiration_key(tx.receiver.encode(), tx.hashlock)

            self.backend.set(self.scratch_table, amount_key, self.encode_balance(tx.amount))
            self.backend.set(self.scratch_table, expiration_key, E.encode(tx.expiration))

            # return the queries for feedback
            return tx, (self.scratch_table, tx.sender.encode(), new_sender_balance), \
                   (self.scratch_table, amount_key, tx.amount), \
                   (self.scratch_table, expiration_key, tx.expiration)
        else:
            return None, None, None, None


class RedeemQuery(SwapQuery):
    def __init__(self, table_name=SWAPS, backend=SQLBackend()):
        super().__init__(table_name=table_name, backend=backend)

    def get_swap(self, address, hashlock):
        # set up table name (scratch if the record does already exist)
        amount_key = self.amount_key(address.encode(), hashlock)
        expiration_key = self.expiration_key(address.encode(), hashlock)

        table = self.table_name
        if self.backend.exists(self.scratch_table, amount_key) and \
                self.backend.exists(self.scratch_table, expiration_key):
            table = self.scratch_table

        # make the queries
        amount = self.backend.get(table, amount_key)
        expiration = self.backend.get(table, expiration_key)

        # return it
        return amount, expiration

    def process_tx(self, tx):
        hashlock = hashlib.sha3_256()
        hashlock.update(tx.secret)
        hashlock = hashlock.digest()

        amount, expiration = self.get_swap(tx.sender, hashlock)

        print(amount, expiration)

        now = int(time.time())

        if amount is not None and E.int(expiration) >= now:
            sender_balance = self.get_balance(tx.sender)

            # add amount to sender balance
            new_sender_balance = sender_balance + int_to_decimal(E.int(amount))
            new_sender_balance = self.encode_balance(new_sender_balance)

            self.backend.set(self.scratch_table, tx.sender.encode(), new_sender_balance)

            # destroy the swap
            amount_key = self.amount_key(tx.sender.encode(), hashlock)
            expiration_key = self.expiration_key(tx.sender.encode(), hashlock)

            self.backend.set(self.scratch_table, amount_key, None)
            self.backend.set(self.scratch_table, expiration_key, None)

            # return the queries for feedback
            return tx, (self.scratch_table, tx.sender.encode(), new_sender_balance), \
                   (self.scratch_table, amount_key, None), \
                   (self.scratch_table, expiration_key, None)
        else:
            return None, None, None, None
