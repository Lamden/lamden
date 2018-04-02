from cilantro.messages.utils import int_to_decimal
from cilantro import Constants
from cilantro.utils import Encoder as E
import hashlib
import time
from cilantro.db.delegate.backend import *


class StateQuery:
    def __init__(self, table_name):
        self.table_name = table_name

    def process_tx(self, tx: dict):
        raise NotImplementedError

    def __str__(self):
        return self.table_name


def select_row(table, key, field, value):
    if key is None:
        key = '*'

    b = SQLBackend()
    b.db.execute('use scratch;')
    q = 'select {} from {} where {}="{}";'.format(key, table, field, value)
    b.db.execute(q)
    r = b.db.fetchone()

    if r is None:
        b.db.execute('use state;')
        q = 'select {} from {} where {}="{}";'.format(key, table, field, value)
        b.db.execute(q)
        r = b.db.fetchone()

    b.context.close()

    if r is None:
        return (None, )

    return r


class StandardQuery(StateQuery):
    """
    StandardQuery
    Automates the state and txq modifications for standard transactions
    """
    def __init__(self, table_name=BALANCES):
        super().__init__(table_name=table_name)
        self.schema = {
            'table': self.table_name,
            'wallet': None,
            'amount': None,
        }

    def process_tx(self, tx):

        row = select_row(BALANCES, 'amount', 'wallet', tx.sender)
        sender_balance = row[0] if row[0] is not None else 0

        print(sender_balance)

        if sender_balance >= tx.amount:

            recv_row = select_row(BALANCES, 'amount', 'wallet', tx.receiver)
            receiver_balance = recv_row[0] if recv_row[0] is not None else 0

            new_sender_balance = sender_balance - tx.amount
            new_receiver_balance = receiver_balance + tx.amount

            deltas = ((tx.sender, new_sender_balance), (tx.receiver, new_receiver_balance))

            return deltas
        else:
            return None


class VoteQuery(StateQuery):
    """
    VoteQuery
    Automates the state modifications for vote transactions
    """
    def __init__(self, table_name=VOTES):
        super().__init__(table_name=table_name)

    def process_tx(self, tx):
        return tx.sender, tx.policy, tx.choice


class SwapQuery(StandardQuery):
    """
    SwapQuery
    Automates the state modifications for swap transactions
    """
    def __init__(self, table_name=SWAPS):
        super().__init__(table_name=table_name)
        self.balance_table = BALANCES

    def process_tx(self, tx):
        sender_balance = select_row('balances', 'amount', 'wallet', tx.sender)[-1]

        if sender_balance >= tx.amount:

            new_sender_balance = sender_balance - tx.amount
            return (tx.sender, new_sender_balance), (tx.sender, tx.receiver, tx.amount, tx.hashlock, tx.expiration)

        else:
            return None


class RedeemQuery(SwapQuery):
    def __init__(self, table_name=SWAPS):
        super().__init__(table_name=table_name)

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
