from cilantro.messages.utils import int_to_decimal
from cilantro.utils import Encoder as E
import hashlib
import time
from cilantro.db.delegate.backend import *

from sqlalchemy import *
from cilantro.db.delegate import tables


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


class StandardQuery:
    """
    StandardQuery
    Automates the state and txq modifications for standard transactions
    """

    def process_tx(self, tx):

        q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.sender)
        q.bind = tables.db

        print(q.compile())

        print(q)

        r = tables.db.execute(q)
        print(r.fetchone())

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


class VoteQuery:
    """
    VoteQuery
    Automates the state modifications for vote transactions
    """

    def process_tx(self, tx):
        q = insert(tables.votes).values(
            wallet=tx.sender,
            policy=tx.policy,
            choice=tx.choice
        )
        return q


class SwapQuery:
    """
    SwapQuery
    Automates the state modifications for swap transactions
    """

    def process_tx(self, tx):
        sender_balance = select_row('balances', 'amount', 'wallet', tx.sender)[-1]

        if sender_balance >= tx.amount:

            new_sender_balance = sender_balance - tx.amount

            balance_q = insert(tables.balances).values(
                wallet=tx.sender,
                amount=new_sender_balance
            )

            swap_q = insert(tables.swaps).values(
                sender=tx.sender,
                receiver=tx.receiver,
                amount=tx.amount,
                expiration=tx.expiration,
                hashlock=tx.hashlock
            )

            return balance_q, swap_q

        else:
            return None


class RedeemQuery:
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
