from unittest import TestCase
from cilantro.db.delegate.backend import *
from cilantro.protocol.interpreters.queries import *
from cilantro.messages import StandardTransaction, StandardTransactionBuilder
from cilantro.utils import Encoder as E
import secrets

class TestQueries(TestCase):
    def mint_coins(self, address, coins):
        b = LevelDBBackend()
        b.set(BALANCES, address.encode(), 0)

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