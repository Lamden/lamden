from unittest import TestCase
from cilantro.messages import StandardTransactionBuilder, VoteTransactionBuilder, SwapTransactionBuilder, RedeemTransactionBuilder
from cilantro import Constants
import secrets
from cilantro.protocol.interpreters.queries import *


global tables
with DB() as db:
    tables = db.tables


class TestQueries(TestCase):
    @staticmethod
    def set_balance(w, a):
        q = insert(tables.balances).values(
            wallet=w,
            amount=a
        )
        execute(q)

    def test_standard_query_get_balance(self):
        a = secrets.token_hex(32)
        self.set_balance(a, 1000000)

        q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == a)
        balance = execute(q).fetchone()

        self.assertEqual(1000000, balance[0])

        a = secrets.token_hex(32)
        self.set_balance(a, 1000000)

        q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == a)
        balance = execute(q).fetchone()

        self.assertEqual(1000000, balance[0])

    def test_standard_process_tx(self):
        std_tx = StandardTransactionBuilder.random_tx()

        self.set_balance(std_tx.sender, std_tx.amount)

        deltas = std_tx.interpret()

        sender_deltas = deltas[0]
        receiver_deltas = deltas[1]

        q = 'UPDATE balances SET '
        q2 = 'INSERT INTO balances (wallet, amount) VALUES '

        self.assertEqual(sender_deltas, q + "amount={} WHERE balances.wallet = '{}'".format(0, std_tx.sender))
        self.assertEqual(receiver_deltas, q2 + "('{}', {})".format(std_tx.receiver, std_tx.amount))

    def test_standard_process_tx_fail(self):
        std_tx = StandardTransactionBuilder.random_tx()

        deltas = std_tx.interpret()
        self.assertEqual(deltas, None)

    def test_vote_process_tx(self):
        vote_tx = VoteTransactionBuilder.random_tx()

        delta = process_vote_tx(vote_tx)

        q = "INSERT INTO votes (wallet, policy, choice) VALUES "

        self.assertEqual(delta[0], q + "('{}', '{}', '{}')".format(vote_tx.sender, vote_tx.policy, vote_tx.choice))

    def test_swap_process_tx(self):
        swap_tx = SwapTransactionBuilder.random_tx()

        self.set_balance(swap_tx.sender, swap_tx.amount)

        deltas = process_swap_tx(swap_tx)

        print(deltas)

        self.assertEqual(deltas[0], "UPDATE balances SET wallet='{}', amount={}".format(swap_tx.sender, 0))
        self.assertEqual(deltas[1], "INSERT INTO swaps (sender, receiver, amount, expiration, hashlock) " 
                                    "VALUES ('{}', '{}', {}, {}, '{}')"
                         .format(swap_tx.sender, swap_tx.receiver, swap_tx.amount, swap_tx.expiration, swap_tx.hashlock))

    def test_redeem_process_tx(self):
        secret = secrets.token_bytes(64)

        h = hashlib.sha3_256()
        h.update(secret)
        lock = h.digest().hex()

        sender_s, sender_v = Constants.Protocol.Wallets.new()
        receiver_s, receiver_v = Constants.Protocol.Wallets.new()

        amount = 123
        expiration = int(time.time()) + 10000

        swap_tx = SwapTransactionBuilder.create_tx(sender_s, sender_v, receiver_v, amount, lock, expiration)

        self.set_balance(swap_tx.sender, swap_tx.amount)

        deltas = process_swap_tx(swap_tx)

        for delta in deltas:
            execute(delta)

        redeem_tx = RedeemTransactionBuilder.create_tx(receiver_s, receiver_v, secret.hex())

        deltas = process_redeem_tx(redeem_tx)

        print(deltas)

        self.assertEqual(deltas[0], "INSERT INTO balances (wallet, amount) VALUES ('{}', {})".format(receiver_v, amount))
        self.assertEqual(deltas[1], "DELETE FROM swaps WHERE swaps.receiver = '{}' AND swaps.hashlock = '{}' "
                                    "AND swaps.amount = {} AND swaps.expiration = '{}'"
                         .format(receiver_v, lock, amount, expiration))

    def test_redeem_process_tx_expires(self):
        secret = secrets.token_bytes(64)

        h = hashlib.sha3_256()
        h.update(secret)
        lock = h.digest().hex()

        sender_s, sender_v = Constants.Protocol.Wallets.new()
        receiver_s, receiver_v = Constants.Protocol.Wallets.new()

        amount = 123
        expiration = int(time.time())

        swap_tx = SwapTransactionBuilder.create_tx(sender_s, sender_v, receiver_v, amount, lock, expiration)

        self.set_balance(swap_tx.sender, swap_tx.amount)

        deltas = process_swap_tx(swap_tx)

        for delta in deltas:
            execute(delta)

        time.sleep(1)

        redeem_tx = RedeemTransactionBuilder.create_tx(sender_s, sender_v, secret.hex())

        deltas = process_redeem_tx(redeem_tx)

        print(deltas)

        self.assertEqual(deltas[0],
                         "INSERT INTO balances (wallet, amount) VALUES ('{}', {})".format(sender_v, amount))
        self.assertEqual(deltas[1], "DELETE FROM swaps WHERE swaps.receiver = '{}' AND swaps.hashlock = '{}' "
                                    "AND swaps.amount = {} AND swaps.expiration = '{}'"
                         .format(sender_v, lock, amount, expiration))