from unittest import TestCase
from cilantro.db.delegate.backend import *
from cilantro.protocol.interpreters.queries import *
from cilantro.messages import StandardTransaction, StandardTransactionBuilder
from cilantro.utils import Encoder as E

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

    def test_standard_query_proper(self):
        std_q = StandardQuery()
        std_tx = StandardTransactionBuilder.random_tx()
        print(std_tx.sender)
        print(std_tx._data.payload.amount)