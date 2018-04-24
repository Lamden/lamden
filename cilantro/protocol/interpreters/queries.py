from cilantro.db.delegate.db import DB, execute, contract
from sqlalchemy import select, insert, update, delete, and_
from cilantro.messages.transaction import *
import hashlib
import time


"""
The @contract(..) decorator will dynamically inject the 'tables' variables into the local namespace of the decorated 
function at time of execution. Thus, this declaration below is just so PyCharm's linter doesn't complain that 'tables' 
is undefined (side stepping those swiggly red lines of shame)  
"""
tables = None


@contract(StandardTransaction)
def process_std_tx(tx):
    print("\n inside process_std_tx \n")

    q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.sender)

    sender_balance = execute(q).fetchone()

    if not sender_balance or not sender_balance[0]:
        return None

    if sender_balance[0] >= tx.amount:

        q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.receiver)

        recv_row = execute(q).fetchone()

        if not recv_row or not recv_row[0]:
            receiver_q = insert(tables.balances).values(
                wallet=tx.receiver,
                amount=tx.amount
            )

        else:
            receiver_q = update(tables.balances).where(tables.balances.c.wallet == tx.receiver)\
                .values(amount=int(recv_row[0]) + tx.amount)

        sender_q = update(tables.balances).where(tables.balances.c.wallet == tx.sender)\
            .values(amount=int(sender_balance[0]) - tx.amount)

        return sender_q, receiver_q
    else:
        return None


@contract(VoteTransaction)
def process_vote_tx(tx):
    q = insert(tables.votes).values(
                wallet=tx.sender,
                policy=tx.policy,
                choice=tx.choice
            )
    return q


@contract(RedeemTransaction)
def process_redeem_tx(tx):
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

    for amount, expiration in execute(q).cursor:
        print(amount, expiration)

        if int(expiration) > int(time.time()):
            # awesome
            q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.sender)

            balance = execute(q).fetchone()

            balance = 0 if balance is None else balance[0]

            new_balance = balance + amount

            q = update(tables.balances).values(
                wallet=tx.sender,
                amount=new_balance
            )

            deltas.append(q)

            q = delete(tables.swaps).where(
                and_(
                    tables.swaps.c.receiver == tx.sender,
                    tables.swaps.c.hashlock == hashlock,
                    tables.swaps.c.amount == amount,
                    tables.swaps.c.expiration == expiration,
                )
            )

            deltas.append(q)

    # check the opposing side. IE, if the sender is the original swap creator and wants a refund

    q = select([tables.swaps.c.amount, tables.swaps.c.expiration, tables.swaps.c.receiver]).where(and_(
        tables.swaps.c.sender == tx.sender,
        tables.swaps.c.hashlock == hashlock
    ))

    for amount, expiration, receiver in execute(q).cursor:
        if int(expiration) < time.time():
            q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.sender)

            balance = execute(q).fetchone() or 0

            new_balance = balance[0] + amount

            q = update(tables.balances).values(
                wallet=tx.sender,
                amount=new_balance
            )

            deltas.append(q)

            q = delete(tables.swaps).where(
                and_(
                    tables.swaps.c.sender == tx.sender,
                    tables.swaps.c.receiver == receiver,
                    tables.swaps.c.hashlock == hashlock,
                    tables.swaps.c.amount == amount,
                    tables.swaps.c.expiration == expiration,
                )
            )
            deltas.append(q)

    if len(deltas) > 0:
        return deltas

    return None


@contract(SwapTransaction)
def process_swap_tx(tx):
    q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.sender)

    row = execute(q).fetchone()

    sender_balance = 0 if not row or not row[0] else row[0]

    if sender_balance >= tx.amount:

        new_sender_balance = sender_balance - tx.amount

        balance_q = update(tables.balances).values(
            wallet=tx.sender,
            amount=int(new_sender_balance)
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


@contract(None)
def process_stamp_tx(tx):
    q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == tx.sender)

    row = execute(q).fetchone()

    sender_balance = 0 if not row or not row[0] else row[0]

    if sender_balance >= tx.amount:

        new_sender_balance = sender_balance - tx.amount

        balance_q = update(tables.balances).values(
            wallet=tx.sender,
            amount=int(new_sender_balance)
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
