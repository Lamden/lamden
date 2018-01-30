from unittest import TestCase
from cilantro.interpreters import TestNetInterpreter
from cilantro.interpreters.constants import *
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
from cilantro.transactions import TestNetTransaction


class TestTestNetInterpreter(TestCase):
    def test_initializing_redis(self):
        try:
            TestNetInterpreter()
        except:
            self.fail(msg='Could not establish connection to Redis.')
        finally:
            self.assertTrue(True)

    def test_basic_success(self):
        (s, v) = ED25519Wallet.new()
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.standard_tx(v, 'jason', '100'), s, use_stamp=False, complete=True)

        try:
            TestNetInterpreter().query_for_transaction(tx)
        except AssertionError:
            self.assertFalse(1 == 1)
        self.assertTrue(1 == 1)

    def test_query_for_std_tx(self):
        (s, v) = ED25519Wallet.new()
        (s2, v2) = ED25519Wallet.new()

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.standard_tx(v, v2, '25'), s, use_stamp=False, complete=True)

        interpreter = TestNetInterpreter()
        interpreter.r.hset('balances', v, '100')
        interpreter.r.hset('balances', v2, '0')

        self.assertEqual(interpreter.r.hget('balances', v), b'100')

        mock_tx = (TestNetTransaction.TX, v, v2, '25')

        query = interpreter.query_for_std_tx(mock_tx)

        mock_query = [
            (HSET, BALANCES, v, 75),
            (HSET, BALANCES, v2, 25)
        ]

        self.assertEqual(query, mock_query)

    def test_query_for_std_tx_bad_query(self):
        (s, v) = ED25519Wallet.new()
        (s2, v2) = ED25519Wallet.new()

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.standard_tx(v, v2, '125'), s, use_stamp=False, complete=True)

        interpreter = TestNetInterpreter()
        interpreter.r.hset('balances', v, '100')
        interpreter.r.hset('balances', v2, '0')

        self.assertEqual(interpreter.r.hget('balances', v), b'100')

        mock_tx = (TestNetTransaction.TX, v, v2, '125')

        try:
            interpreter.query_for_std_tx(mock_tx)
            self.assertTrue(False)
        except AssertionError:
            self.assertTrue(True)

