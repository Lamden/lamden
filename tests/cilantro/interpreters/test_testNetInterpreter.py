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
            TestNetInterpreter().r.hset(BALANCES, v, '100')
            TestNetInterpreter().query_for_transaction(tx)
        except AssertionError:
            self.assertTrue(False)
        self.assertTrue(True)

    def test_basic_failure_at_first_assertion_point(self):
        (s, v) = ED25519Wallet.new()
        TestNetInterpreter().r.hset(BALANCES, v, '100')
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.standard_tx(v, 'jason', '1000'), s, use_stamp=False, complete=True)
        try:
            TestNetInterpreter().query_for_transaction(tx)
            self.assertTrue(False)
        except:
            self.assertTrue(True)

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

    def test_query_for_vote_tx(self):
        (s, v) = ED25519Wallet.new()
        (s2, v2) = ED25519Wallet.new()

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.vote_tx(v, v2), s, use_stamp=False, complete=True)

        interpreter = TestNetInterpreter()

        mock_tx = (TestNetTransaction.VOTE, v, v2)

        query = interpreter.query_for_vote_tx(mock_tx)

        mock_query = [
            (HSET, VOTES, v, v2),
        ]

        self.assertEqual(query, mock_query)

    def test_query_for_stamp_tx_add(self):
        (s, v) = ED25519Wallet.new()
        (s2, v2) = ED25519Wallet.new()

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.stamp_tx(v, '25'), s, use_stamp=False, complete=True)

        interpreter = TestNetInterpreter()
        interpreter.r.hset('balances', v, '100')

        self.assertEqual(interpreter.r.hget('balances', v), b'100')

        mock_tx = (TestNetTransaction.STAMP, v, '25')

        query = interpreter.query_for_stamp_tx(mock_tx)

        mock_query = [
            (HSET, BALANCES, v, 75),
            (HSET, STAMPS, v, 25)
        ]

        self.assertEqual(query, mock_query)

    def test_query_for_stamp_tx_bad_query(self):
        (s, v) = ED25519Wallet.new()

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.stamp_tx(v, '125'), s, use_stamp=False, complete=True)

        interpreter = TestNetInterpreter()
        interpreter.r.hset('balances', v, '100')

        self.assertEqual(interpreter.r.hget('balances', v), b'100')

        mock_tx = (TestNetTransaction.STAMP, v, '125')

        try:
            interpreter.query_for_stamp_tx(mock_tx)
            self.assertTrue(False)
        except AssertionError:
            self.assertTrue(True)

    def test_query_for_stamp_tx_sub(self):
        (s, v) = ED25519Wallet.new()

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.stamp_tx(v, '-25'), s, use_stamp=False, complete=True)

        interpreter = TestNetInterpreter()
        interpreter.r.hset(STAMPS, v, '100')

        self.assertEqual(interpreter.r.hget(STAMPS, v), b'100')

        mock_tx = (TestNetTransaction.STAMP, v, '-25')

        query = interpreter.query_for_stamp_tx(mock_tx)

        mock_query = [
            (HSET, STAMPS, v, 75),
            (HSET, BALANCES, v, 25)
        ]

        self.assertEqual(query, mock_query)

    def test_query_for_stamp_tx_sub_bad_query(self):
        (s, v) = ED25519Wallet.new()

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.stamp_tx(v, '-125'), s, use_stamp=False, complete=True)

        interpreter = TestNetInterpreter()
        interpreter.r.hset(STAMPS, v, '100')

        self.assertEqual(interpreter.r.hget(STAMPS, v), b'100')

        mock_tx = (TestNetTransaction.STAMP, v, '-125')

        try:
            interpreter.query_for_stamp_tx(mock_tx)
            self.assertTrue(False)
        except AssertionError:
            self.assertTrue(True)

    def test_query_for_invalid_tx_type(self):
        (s, v) = ED25519Wallet.new()

        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.stamp_tx(v, '-125'), s, use_stamp=False, complete=True)
        tx.payload['payload'] = ('FAKE', v, '-125')

        interpreter = TestNetInterpreter()
        query = interpreter.query_for_transaction(tx)

        self.assertEqual(query, FAIL)
