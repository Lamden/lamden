from unittest import TestCase
from cilantro.messages import StandardTransactionBuilder, VoteTransactionBuilder, SwapTransactionBuilder, RedeemTransactionBuilder
from cilantro.utils import Encoder as E
from cilantro import Constants
import secrets
from cilantro.protocol.interpreters.queries import *


class TestQueries(TestCase):
    @staticmethod
    def set_balance(w, db: str, a):
        tables.db.execute('use {}'.format(db))
        q = insert(tables.balances).values(
            wallet=w,
            amount=a
        )
        tables.db.execute(q)

    def test_standard_query_get_balance(self):
        a = secrets.token_hex(64)
        self.set_balance(a, 'state', 1000000)

        q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == a)
        balance = tables.db.execute(q).fetchone()

        self.assertEqual(1000000, balance[0])

        a = secrets.token_hex(64)
        self.set_balance(a, 'scratch', 1000000)

        q = select([tables.balances.c.amount]).where(tables.balances.c.wallet == a)
        balance = tables.db.execute(q).fetchone()

        self.assertEqual(1000000, balance[0])

    def test_standard_process_tx(self):
        std_q = StandardQuery()
        std_tx = StandardTransactionBuilder.random_tx()

        self.set_balance(std_tx.sender, 'state', std_tx.amount)

        deltas = std_q.process_tx(std_tx)

        sender_deltas = deltas[0]
        receiver_deltas = deltas[1]

        q = 'INSERT INTO balances (wallet, amount) VALUES '

        self.assertEqual(sender_deltas, q + "('{}', {})".format(std_tx.sender, 0))
        self.assertEqual(receiver_deltas, q + "('{}', {})".format(std_tx.receiver, std_tx.amount))

    def test_standard_process_tx_fail(self):
        std_q = StandardQuery()
        std_tx = StandardTransactionBuilder.random_tx()

        deltas = std_q.process_tx(std_tx)
        self.assertEqual(deltas, None)

    def test_vote_process_tx(self):
        vote_q = VoteQuery()
        vote_tx = VoteTransactionBuilder.random_tx()

        delta = vote_q.process_tx(vote_tx)

        q = "INSERT INTO votes (wallet, policy, choice) VALUES "

        self.assertEqual(delta[0], q + "('{}', '{}', '{}')".format(vote_tx.sender, vote_tx.policy, vote_tx.choice))

    def test_swap_process_tx(self):
        swap_q = SwapQuery()
        swap_tx = SwapTransactionBuilder.random_tx()

        self.set_balance(swap_tx.sender, 'state', swap_tx.amount)

        deltas = swap_q.process_tx(swap_tx)

        self.assertEqual(deltas[0], "INSERT INTO balances (wallet, amount) VALUES ('{}', {})".format(swap_tx.sender, 0))
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

        swap_q = SwapQuery()
        swap_tx = SwapTransactionBuilder.create_tx(sender_s, sender_v, receiver_v, amount, lock, expiration)

        self.set_balance(swap_tx.sender, 'state', swap_tx.amount)

        deltas = swap_q.process_tx(swap_tx)

        for delta in deltas:
            tables.db.execute(delta)

        redeem_q = RedeemQuery()

        redeem_tx = RedeemTransactionBuilder.create_tx(receiver_s, receiver_v, secret.hex())

        deltas = redeem_q.process_tx(redeem_tx)

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

        swap_q = SwapQuery()
        swap_tx = SwapTransactionBuilder.create_tx(sender_s, sender_v, receiver_v, amount, lock, expiration)

        self.set_balance(swap_tx.sender, 'state', swap_tx.amount)

        deltas = swap_q.process_tx(swap_tx)

        for delta in deltas:
            tables.db.execute(delta)

        time.sleep(1)

        redeem_q = RedeemQuery()

        redeem_tx = RedeemTransactionBuilder.create_tx(sender_s, sender_v, secret.hex())

        deltas = redeem_q.process_tx(redeem_tx)

        print(deltas)

        self.assertEqual(deltas[0],
                         "INSERT INTO balances (wallet, amount) VALUES ('{}', {})".format(sender_v, amount))
        self.assertEqual(deltas[1], "DELETE FROM swaps WHERE swaps.receiver = '{}' AND swaps.hashlock = '{}' "
                                    "AND swaps.amount = {} AND swaps.expiration = '{}'"
                         .format(sender_v, lock, amount, expiration))