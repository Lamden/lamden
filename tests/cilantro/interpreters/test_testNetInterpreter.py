from unittest import TestCase
from cilantro.interpreters import TestNetInterpreter
from cilantro.interpreters.constants import *
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
from cilantro.transactions import TestNetTransaction
import secrets
import hashlib

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

    def test_query_for_swap_tx(self):
        # create new wallet
        (s, v) = ED25519Wallet.new()

        # create the mock tx data
        RECIPIENT = 'davis'
        AMOUNT = '100'

        secret = secrets.token_hex(16)
        hash = hashlib.new('ripemd160')
        hash.update(bytes.fromhex(secret))

        HASH_LOCK = hash.digest().hex()
        UNIX_EXPIRATION = '1000'

        # build the transaction
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.swap_tx(v, RECIPIENT, AMOUNT, HASH_LOCK, UNIX_EXPIRATION),
                 s, use_stamp=False, complete=True)

        # initialize the interpreter
        interpreter = TestNetInterpreter()

        # add some coinage
        interpreter.r.hset(BALANCES, v, AMOUNT)

        # query
        query = interpreter.query_for_transaction(tx)

        # create what the output should be
        mock_query = [
            (HSET, BALANCES, v, 0),
            (HMSET, SWAP, HASH_LOCK, v, RECIPIENT, AMOUNT, UNIX_EXPIRATION),
        ]

        # assert true or not
        self.assertEqual(query, mock_query)

    def test_query_for_low_balance_swap_tx(self):
        # create new wallet
        (s, v) = ED25519Wallet.new()

        # create the mock tx data
        RECIPIENT = 'davis'
        AMOUNT = '100'

        secret = secrets.token_hex(16)
        hash = hashlib.new('ripemd160')
        hash.update(bytes.fromhex(secret))

        HASH_LOCK = hash.digest().hex()
        UNIX_EXPIRATION = '1000'

        # build the transaction
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.swap_tx(v, RECIPIENT, AMOUNT, HASH_LOCK, UNIX_EXPIRATION),
                 s, use_stamp=False, complete=True)

        # initialize the interpreter
        interpreter = TestNetInterpreter()

        # add some coinage
        #interpreter.r.hset(BALANCES, v, AMOUNT)

        # query
        query = interpreter.query_for_transaction(tx)

        # create what the output should be
        mock_query = FAIL

        # assert true or not
        self.assertEqual(query, mock_query)

    def test_query_for_bad_swap_tx(self):
        # create new wallet
        (s, v) = ED25519Wallet.new()

        # create the mock tx data
        RECIPIENT = 'davis'
        AMOUNT = '100'

        secret = secrets.token_hex(16)
        hash = hashlib.new('ripemd160')
        hash.update(bytes.fromhex(secret))
        HASH_LOCK = hash.digest().hex()
        UNIX_EXPIRATION = '1000'

        # build the transaction
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.swap_tx(v, RECIPIENT, AMOUNT, HASH_LOCK, UNIX_EXPIRATION),
                 s, use_stamp=False, complete=True)

        # initialize the interpreter
        interpreter = TestNetInterpreter()

        # add the record
        interpreter.r.hset(BALANCES, v, AMOUNT)
        interpreter.r.hmset(HASH_LOCK, {'sender': v,
                                        'recipient': RECIPIENT,
                                        'amount': AMOUNT,
                                        'unix_expiration': UNIX_EXPIRATION})

        # query
        query = interpreter.query_for_transaction(tx)

        # create what the output should be
        mock_query = FAIL
        # assert true or not
        self.assertEqual(query, mock_query)

    def test_query_for_redeem_tx(self):
        # create new wallets for sender and reciever
        (sender_priv_key, sender_pub_key) = ED25519Wallet.new()
        (recipient_priv_key, recipient_pub_key) = ED25519Wallet.new()

        # create a swap to redeem
        AMOUNT = '1000'
        UNIX_EXPIRATION = '10000'

        SECRET = secrets.token_hex(16)

        hash = hashlib.new('ripemd160')
        hash.update(bytes.fromhex(SECRET))

        HASH_LOCK = hash.digest().hex()

        interpreter = TestNetInterpreter()
        interpreter.r.hset(BALANCES, sender_pub_key, AMOUNT)
        interpreter.r.hset(BALANCES, recipient_pub_key, '100')
        interpreter.r.hmset(HASH_LOCK, {
            'sender': sender_pub_key,
            'recipient': recipient_pub_key,
            'amount': AMOUNT,
            'unix_expiration': UNIX_EXPIRATION
        })

        # create the redeem script
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.redeem_tx(SECRET), recipient_priv_key, use_stamp=False, complete=True)

        # create the mock query of how it should work
        mock_query = [
            (HSET, BALANCES, recipient_pub_key, 1100),
            (DEL, HASH_LOCK)
        ]

        query = interpreter.query_for_redeem_tx(tx.payload['payload'], tx.payload['metadata'])

        # assert true or not
        self.assertEqual(query, mock_query)

    def test_query_for_bad_secret_redeem(self):
        # create new wallets for sender and reciever
        (sender_priv_key, sender_pub_key) = ED25519Wallet.new()
        (recipient_priv_key, recipient_pub_key) = ED25519Wallet.new()

        # create a swap to redeem
        AMOUNT = '1000'
        UNIX_EXPIRATION = '10000'

        SECRET = secrets.token_hex(16)

        hash = hashlib.new('ripemd160')
        hash.update(bytes.fromhex(SECRET))

        HASH_LOCK = hash.digest().hex()

        interpreter = TestNetInterpreter()
        interpreter.r.hset(BALANCES, sender_pub_key, AMOUNT)
        interpreter.r.hset(BALANCES, recipient_pub_key, '100')
        interpreter.r.hmset(HASH_LOCK, {
            'sender': sender_pub_key,
            'recipient': recipient_pub_key,
            'amount': AMOUNT,
            'unix_expiration': UNIX_EXPIRATION
        })

        # create the redeem script
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.redeem_tx('ABCD'), recipient_priv_key, use_stamp=False, complete=True)

        # create the mock query of how it should work
        mock_query = FAIL

        query = interpreter.query_for_redeem_tx(tx.payload['payload'], tx.payload['metadata'])

        # assert true or not
        self.assertEqual(query, mock_query)

    def test_query_for_bad_signature_redeem(self):
        # create new wallets for sender and reciever
        (sender_priv_key, sender_pub_key) = ED25519Wallet.new()
        (recipient_priv_key, recipient_pub_key) = ED25519Wallet.new()
        (attacker_priv_key, attacker_pub_key) = ED25519Wallet.new()

        # create a swap to redeem
        AMOUNT = '1000'
        UNIX_EXPIRATION = '10000'

        SECRET = secrets.token_hex(16)

        hash = hashlib.new('ripemd160')
        hash.update(bytes.fromhex(SECRET))

        HASH_LOCK = hash.digest().hex()

        interpreter = TestNetInterpreter()
        interpreter.r.hset(BALANCES, sender_pub_key, AMOUNT)
        interpreter.r.hset(BALANCES, recipient_pub_key, '100')
        interpreter.r.hmset(HASH_LOCK, {
            'sender': sender_pub_key,
            'recipient': recipient_pub_key,
            'amount': AMOUNT,
            'unix_expiration': UNIX_EXPIRATION
        })

        # create the redeem script
        tx = TestNetTransaction(ED25519Wallet, SHA3POW)
        tx.build(TestNetTransaction.redeem_tx(SECRET), attacker_priv_key, use_stamp=False, complete=True)

        # create the mock query of how it should work
        mock_query = FAIL

        query = interpreter.query_for_redeem_tx(tx.payload['payload'], tx.payload['metadata'])

        # assert true or not
        self.assertEqual(query, mock_query)