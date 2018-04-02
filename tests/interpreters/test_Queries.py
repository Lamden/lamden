from unittest import TestCase
from cilantro.protocol.interpreters.queries import *
from cilantro.messages import StandardTransactionBuilder, VoteTransactionBuilder, SwapTransactionBuilder, RedeemTransactionBuilder
from cilantro.utils import Encoder as E
from cilantro import Constants
import secrets
import hashlib


class TestQueries(TestCase):
    @staticmethod
    def set_balance(wallet, db: str, amount):
        b = SQLBackend()
        b.db.execute('use {};'.format(db))
        b.replace(BALANCES, '(wallet, amount)', (wallet, amount))
        b.db = b.context.close()

    def test_standard_query_get_balance(self):
        a = secrets.token_hex(64)
        self.set_balance(a, 'state', 1000000)
        balance = select_row('balances', 'amount', 'wallet', a)

        self.assertIn(1000000, balance)

        aa = secrets.token_hex(64)
        self.set_balance(aa, 'scratch', 1000000)
        balance_scratch = select_row('balances', 'amount', 'wallet', aa)

        self.assertIn(1000000, balance_scratch)

    def test_standard_process_tx(self):
        std_q = StandardQuery()
        std_tx = StandardTransactionBuilder.random_tx()

        self.set_balance(std_tx.sender, 'state', std_tx.amount)

        deltas = std_q.process_tx(std_tx)

        sender_deltas = deltas[0]
        receiver_deltas = deltas[1]

        self.assertEqual(sender_deltas[-1], 0)
        self.assertEqual(receiver_deltas[-1], std_tx.amount)

    def test_standard_process_tx_fail(self):
        std_q = StandardQuery()
        std_tx = StandardTransactionBuilder.random_tx()

        deltas = std_q.process_tx(std_tx)
        self.assertEqual(deltas, None)

    def test_vote_process_tx(self):
        vote_q = VoteQuery()
        vote_tx = VoteTransactionBuilder.random_tx()

        delta = vote_q.process_tx(vote_tx)

        self.assertEqual(delta[0], vote_tx.sender)
        self.assertEqual(delta[1], vote_tx.policy)
        self.assertEqual(delta[2], vote_tx.choice)

    def test_swap_process_tx(self):
        swap_q = SwapQuery()
        swap_tx = SwapTransactionBuilder.random_tx()

        b = SQLBackend()
        self.set_balance(swap_tx.sender, 'state', swap_tx.amount)

        swap_q.process_tx(swap_tx)

        # test that the changes have been made to scratch

        new_sender_value = select_row('balances', 'amount', 'wallet', swap_tx.sender)

        # new_sender_value = b.get(SEPARATOR.join([SCRATCH, BALANCES]), swap_tx.sender.encode())
        # new_receiver_value = b.get(SEPARATOR.join([SCRATCH, SWAPS]), swap_q.amount_key(swap_tx.receiver.encode(), swap_tx.hashlock))
        # expiration_date = b.get(SEPARATOR.join([SCRATCH, SWAPS]), swap_q.expiration_key(swap_tx.receiver.encode(), swap_tx.hashlock))
        #
        # new_sender_value = E.int(new_sender_value)
        # new_receiver_value = int_to_decimal(E.int(new_receiver_value))
        # expiration_date = E.int(expiration_date)

        self.assertEqual(new_sender_value, 0)
        # self.assertEqual(new_receiver_value, swap_tx.amount)
        # self.assertEqual(expiration_date, swap_tx.expiration)

    def test_redeem_get_swap(self):
        secret = secrets.token_bytes(64)

        h = hashlib.sha3_256()
        h.update(secret)
        lock = h.digest()

        sender_s, sender_v = Constants.Protocol.Wallets.new()
        receiver_s, receiver_v = Constants.Protocol.Wallets.new()

        swap_q = SwapQuery()
        swap_tx = SwapTransactionBuilder.create_tx(sender_s, sender_v, receiver_v, 123, lock, int(time.time()) + 10000)

        b = SQLBackend()
        b.set(BALANCES, swap_tx.sender.encode(), SwapQuery.encode_balance(swap_tx.amount))

        swap_q.process_tx(swap_tx)

        redeem_q = RedeemQuery()
        amount, expiration = redeem_q.get_swap(receiver_v, lock)

        self.assertEqual(amount, SwapQuery.encode_balance(swap_tx.amount))
        self.assertEqual(E.int(expiration), swap_tx.expiration)

    def test_redeem_process_tx(self):
        secret = secrets.token_bytes(64)

        h = hashlib.sha3_256()
        h.update(secret)
        lock = h.digest()

        sender_s, sender_v = Constants.Protocol.Wallets.new()
        receiver_s, receiver_v = Constants.Protocol.Wallets.new()

        swap_q = SwapQuery()
        swap_tx = SwapTransactionBuilder.create_tx(sender_s, sender_v, receiver_v, 123, lock, int(time.time()) + 10000)

        b = SQLBackend()
        b.set(BALANCES, swap_tx.sender.encode(), SwapQuery.encode_balance(swap_tx.amount))

        swap_q.process_tx(swap_tx)

        redeem_q = RedeemQuery()
        redeem_tx = RedeemTransactionBuilder.create_tx(receiver_s, receiver_v, secret)

        amount, _ = redeem_q.get_swap(receiver_v, lock)

        tx, sender_scratch, amount_scratch, expiration_scratch = redeem_q.process_tx(redeem_tx)

        self.assertEqual(RedeemQuery().encode_balance(123), amount)
        self.assertEqual(expiration_scratch[-1], None)

    def test_redeem_process_tx_expires(self):
        secret = secrets.token_bytes(64)

        h = hashlib.sha3_256()
        h.update(secret)
        lock = h.digest()

        sender_s, sender_v = Constants.Protocol.Wallets.new()
        receiver_s, receiver_v = Constants.Protocol.Wallets.new()

        swap_q = SwapQuery()
        swap_tx = SwapTransactionBuilder.create_tx(sender_s, sender_v, receiver_v, 123, lock, int(time.time()))

        b = SQLBackend()
        b.set(BALANCES, swap_tx.sender.encode(), SwapQuery.encode_balance(swap_tx.amount))

        swap_q.process_tx(swap_tx)

        redeem_q = RedeemQuery()
        redeem_tx = RedeemTransactionBuilder.create_tx(receiver_s, receiver_v, secret)

        time.sleep(1)

        tx, sender_scratch, amount_scratch, expiration_scratch = redeem_q.process_tx(redeem_tx)

        self.assertEqual(tx, None)
        self.assertEqual(sender_scratch, None)
        self.assertEqual(amount_scratch, None)
        self.assertEqual(expiration_scratch, None)