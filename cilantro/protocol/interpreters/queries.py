import hashlib
import time

from sqlalchemy import *
from cilantro.db.delegate import tables



class StandardQuery:
    """
    StandardQuery
    Automates the state and txq modifications for standard transactions
    """

    def process_tx(self, tx):

        q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.sender)

        row = tables.db.execute(q).fetchone()

        sender_balance = row[0] if row[0] is not None else 0

        print(sender_balance)

        if sender_balance >= tx.amount:

            q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.receiver)

            recv_row = tables.db.execute(q).fetchone()

            receiver_balance = recv_row[0] if recv_row[0] is not None else 0

            new_sender_balance = sender_balance - tx.amount
            new_receiver_balance = receiver_balance + tx.amount

            sender_q = insert(tables.balances).values(
                wallet=tx.sender,
                amount=new_sender_balance
            )

            receiver_q = insert(tables.balances).values(
                wallet=tx.receiver,
                amount=new_receiver_balance
            )

            return sender_q, receiver_q
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
    Rules:
    Sender cannot overwrite this value / update it, so fail if the swap cannot insert (on interpreter side?)
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

    def process_tx(self, tx):
        # calculate the hashlock from the secret. if it is incorrect, the query will fail
        hashlock = hashlib.sha3_256()
        hashlock.update(bytes.fromhex(tx.secret))
        hashlock = hashlock.digest().hex()

        # build the query assuming that this is a redeem, not a refund
        q = select([tables.swaps.c.amount, tables.swaps.c.expiration]).where(and_(
            tables.swaps.c.receiver == tx.sender,
            tables.swaps.c.hashlock == hashlock
        ))

        # get the data from the db. let's assume that people reuse secrets (BAD!), and so we will iterate through
        # all of the queries we got back.

        deltas = []

        for amount, expiration in tables.db.execute(q).cursor:
            if expiration > time.time():
                # awesome
                q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.sender)

                balance = tables.db.execute(q).fetchone()

                new_balance = balance + amount

                q = insert(tables.balances).values(
                    wallet=tx.sender,
                    amount=new_balance
                )

                deltas.append(q)

                q = delete(tables.swaps).where(
                    tables.swaps.c.receiver == tx.sender,
                    tables.swaps.c.hashlock == hashlock,
                    tables.swaps.c.amount == amount,
                    tables.swaps.c.expiration == expiration,
                )

                deltas.append(q)

        # check the opposing side. IE, if the sender is the original swap creator and wants a refund

        q = select([tables.swaps.c.amount, tables.swaps.c.expiration]).where(and_(
            tables.swaps.c.sender == tx.sender,
            tables.swaps.c.hashlock == hashlock
        ))

        for amount, expiration in tables.db.execute(q).cursor:
            if expiration < time.time():
                q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.sender)

                balance = tables.db.execute(q).fetchone()

                new_balance = balance + amount

                q = insert(tables.balances).values(
                    wallet=tx.sender,
                    amount=new_balance
                )

                deltas.append(q)

                q = delete(tables.swaps).where(
                    tables.swaps.c.receiver == tx.sender,
                    tables.swaps.c.hashlock == hashlock,
                    tables.swaps.c.amount == amount,
                    tables.swaps.c.expiration == expiration,
                )

                deltas.append(q)

        if len(deltas) > 0:
            return deltas

        return None
