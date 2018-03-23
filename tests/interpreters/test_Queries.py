from unittest import TestCase
from cilantro.protocol.interpreters.queries import *
from cilantro.messages import StandardTransactionBuilder, VoteTransactionBuilder, SwapTransactionBuilder, RedeemTransactionBuilder
from cilantro.utils import Encoder as E
from cilantro import Constants
import secrets
import hashlib


class TestQueries(TestCase):

    def test_state_query_string(self):
        t = b'some_table'
        l = LevelDBBackend()
        sq = StateQuery(t, l)

        self.assertEqual(str(sq), t.decode())

    def test_state_query_implemented_error(self):
        t = b'some_table'
        l = LevelDBBackend()
        sq = StateQuery(t, l)

        def process_tx():
            sq.process_tx({1: 2})

        self.assertRaises(NotImplementedError, process_tx)

    def test_standard_query_balance_encode_decode(self):
        b = LevelDBBackend()
        a = secrets.token_hex(64)
        b.set(BALANCES, a.encode(), E.encode(1000000))

        balance = StandardQuery().balance_to_decimal(BALANCES, a)
        self.assertEqual(balance, 100.0000)
        self.assertEqual(StandardQuery.encode_balance(balance), E.encode(1000000))

    def test_standard_query_get_balance(self):
        b = LevelDBBackend()
        a = secrets.token_hex(64)
        b.set(BALANCES, a.encode(), E.encode(1000000))

        balance = StandardQuery().get_balance(a)

        self.assertEqual(balance, 100.0000)

        aa = secrets.token_hex(64)
        b.set(SCRATCH+SEPARATOR+BALANCES, aa.encode(), E.encode(1000000))

        balance_scratch = StandardQuery().get_balance(aa)

        self.assertEqual(balance_scratch, 100.0000)

    def test_standard_process_tx(self):
        std_q = StandardQuery()
        std_tx = StandardTransactionBuilder.random_tx()

        b = LevelDBBackend()
        b.set(BALANCES, std_tx.sender.encode(), StandardQuery.encode_balance(std_tx.amount))

        std_q.process_tx(std_tx)

        # test that the changes have been made to scratch
        new_sender_value = b.get(SEPARATOR.join([SCRATCH, BALANCES]), std_tx.sender.encode())
        new_receiver_value = b.get(SEPARATOR.join([SCRATCH, BALANCES]), std_tx.receiver.encode())

        new_sender_value = E.int(new_sender_value)
        new_receiver_value = int_to_decimal(E.int(new_receiver_value))

        self.assertEqual(new_sender_value, 0)
        self.assertEqual(new_receiver_value, std_tx.amount)

    def test_standard_process_tx_fail(self):
        std_q = StandardQuery()
        std_tx = StandardTransactionBuilder.random_tx()

        tx, sender, receiver = std_q.process_tx(std_tx)
        self.assertEqual(tx, None)
        self.assertEqual(sender, None)
        self.assertEqual(receiver, None)

    def test_vote_process_tx(self):
        vote_q = VoteQuery()
        vote_tx = VoteTransactionBuilder.random_tx()

        tx, scratch = vote_q.process_tx(vote_tx)

        self.assertEqual(scratch[1], vote_tx.policy.encode() + SEPARATOR + vote_tx.sender.encode())
        self.assertEqual(scratch[2], vote_tx.choice.encode())

    def test_vote_fail(self):
        vote_q = VoteQuery()

        tx, scratch = vote_q.process_tx(b'')

        self.assertEqual(tx, None)
        self.assertEqual(scratch, None)

    def test_swap_amount_key(self):
        a = secrets.token_bytes(16)
        h = secrets.token_bytes(16)

        self.assertEqual(SwapQuery.amount_key(a, h), a + SEPARATOR + h + SEPARATOR + b'amount')

    def test_swap_expiration_key(self):
        a = secrets.token_bytes(16)
        h = secrets.token_bytes(16)

        self.assertEqual(SwapQuery.expiration_key(a, h), a + SEPARATOR + h + SEPARATOR + b'expiration')

    def test_swap_process_tx(self):
        swap_q = SwapQuery()
        swap_tx = SwapTransactionBuilder.random_tx()

        b = LevelDBBackend()
        b.set(BALANCES, swap_tx.sender.encode(), SwapQuery.encode_balance(swap_tx.amount))

        swap_q.process_tx(swap_tx)

        # test that the changes have been made to scratch
        new_sender_value = b.get(SEPARATOR.join([SCRATCH, BALANCES]), swap_tx.sender.encode())
        new_receiver_value = b.get(SEPARATOR.join([SCRATCH, SWAPS]), swap_q.amount_key(swap_tx.receiver.encode(), swap_tx.hashlock))
        expiration_date = b.get(SEPARATOR.join([SCRATCH, SWAPS]), swap_q.expiration_key(swap_tx.receiver.encode(), swap_tx.hashlock))

        new_sender_value = E.int(new_sender_value)
        new_receiver_value = int_to_decimal(E.int(new_receiver_value))
        expiration_date = E.int(expiration_date)

        self.assertEqual(new_sender_value, 0)
        self.assertEqual(new_receiver_value, swap_tx.amount)
        self.assertEqual(expiration_date, swap_tx.expiration)

    def test_redeem_get_swap(self):
        secret = secrets.token_bytes(64)

        h = hashlib.sha3_256()
        h.update(secret)
        lock = h.digest()

        sender_s, sender_v = Constants.Protocol.Wallets.new()
        receiver_s, receiver_v = Constants.Protocol.Wallets.new()

        swap_q = SwapQuery()
        swap_tx = SwapTransactionBuilder.create_tx(sender_s, sender_v, receiver_v, 123, lock, int(time.time()) + 10000)

        b = LevelDBBackend()
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

        b = LevelDBBackend()
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

        b = LevelDBBackend()
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