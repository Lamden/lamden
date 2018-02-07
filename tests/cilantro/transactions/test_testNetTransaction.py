from unittest import TestCase
from cilantro.transactions import TestNetTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import SHA3POW

'''
    Things to test:
    If transactions get built correctly.
        Types:
        Standard - ✔︎
        Vote - ✔︎
        Stamp - ✔︎
    If signing works.  - ✔︎
    If POW puzzle works. - ✔︎
    If stamping works. - ✔︎
    
    Let's do it :)
    
    Do transactions need to say who it's from if they are signing it?
    Probably not...
'''

class TestTestNetTransaction(TestCase):

    def test_standard_tx_build(self):
        FROM = 'stuart'
        TO = 'jason'
        AMOUNT = '100'

        std_should_be = (TestNetTransaction.TX, FROM, TO, AMOUNT)

        self.assertEqual(std_should_be, TestNetTransaction.standard_tx(FROM, TO, AMOUNT))

    def test_stamp_tx_build(self):
        FROM = 'stuart'
        AMOUNT = '1000'

        stamp_should_be = (TestNetTransaction.STAMP, FROM, AMOUNT)

        self.assertEqual(stamp_should_be, TestNetTransaction.stamp_tx(FROM, AMOUNT))

    def test_vote_tx_build(self):
        FROM = 'stuart'
        CANDIDATE = 'jason'

        vote_should_be = (TestNetTransaction.VOTE, FROM, CANDIDATE)

        self.assertEqual(vote_should_be, TestNetTransaction.vote_tx(FROM, CANDIDATE))

    def test_sign_std_tx(self):
        (s, v) = ED25519Wallet.new()
        TO = 'jason'
        AMOUNT = '1001'

        tx = TestNetTransaction.standard_tx(v, TO, AMOUNT)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=SHA3POW)
        transaction_factory.build(tx, s, complete=True, use_stamp=True)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']
        self.assertTrue(TestNetTransaction.verify_tx(full_tx, v, sig, ED25519Wallet, SHA3POW))

    def test_sign_std_tx_pow(self):
        (s, v) = ED25519Wallet.new()
        TO = 'jason'
        AMOUNT = '1001'

        tx = TestNetTransaction.standard_tx(v, TO, AMOUNT)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=SHA3POW)
        transaction_factory.build(tx, s, complete=True, use_stamp=False)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        proof = full_tx['metadata']['proof']
        self.assertTrue(SHA3POW.check(str(full_tx['payload']).encode(), proof))
        self.assertTrue(TestNetTransaction.verify_tx(full_tx, v, sig, ED25519Wallet, SHA3POW))

    def test_stamp_std_tx(self):
        (s, v) = ED25519Wallet.new()
        AMOUNT = '1000'

        tx = TestNetTransaction.stamp_tx(v, AMOUNT)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=SHA3POW)
        transaction_factory.build(tx, s, complete=True, use_stamp=True)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        self.assertTrue(TestNetTransaction.verify_tx(full_tx, v, sig, ED25519Wallet, SHA3POW))

    def test_stamp_std_tx_pow(self):
        (s, v) = ED25519Wallet.new()
        AMOUNT = '1000'

        tx = TestNetTransaction.stamp_tx(v, AMOUNT)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=SHA3POW)
        transaction_factory.build(tx, s, complete=True, use_stamp=False)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        proof = full_tx['metadata']['proof']

        self.assertTrue(SHA3POW.check(str(full_tx['payload']).encode(), proof))
        self.assertTrue(TestNetTransaction.verify_tx(full_tx, v, sig, ED25519Wallet, SHA3POW))

    def test_stamp_vote_tx(self):
        (s, v) = ED25519Wallet.new()
        CANDIDATE = 'jason'

        tx = TestNetTransaction.vote_tx(v, CANDIDATE)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=SHA3POW)
        transaction_factory.build(tx, s, complete=True, use_stamp=True)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        self.assertTrue(transaction_factory.verify_tx(full_tx, v, sig, ED25519Wallet, SHA3POW))

    def test_stamp_std_tx_pow(self):
        (s, v) = ED25519Wallet.new()
        CANDIDATE = 'jason'

        tx = TestNetTransaction.vote_tx(v, CANDIDATE)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=SHA3POW)
        transaction_factory.build(tx, s, complete=True, use_stamp=False)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        proof = full_tx['metadata']['proof']

        self.assertTrue(SHA3POW.check(str(full_tx['payload']).encode(), proof))
        self.assertTrue(TestNetTransaction.verify_tx(full_tx, v, sig, ED25519Wallet, SHA3POW))