from unittest import TestCase
from cilantro.transactions import TestNetTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import TwofishPOW

'''
    Things to test:
    If transactions get built correctly.
        Types:
        Standard - ✔︎
        Vote - ✔︎
        Stamp - ✔︎
    If signing works.
    If POW puzzle works.
    If stamping works.
    
    Let's do it :)
    
    Do transactions need to say who it's from if they are signing it?
    Probably not...
'''

class TestTestNetTransaction(TestCase):

    def test_standard_tx_build(self):
        TO = 'jason'
        AMOUNT = '100'

        std_should_be = (TestNetTransaction.TX, TO, AMOUNT)

        self.assertEqual(std_should_be, TestNetTransaction.standard_tx(TO, AMOUNT))

    def test_stamp_tx_build(self):
        AMOUNT = '1000'

        stamp_should_be = (TestNetTransaction.STAMP, AMOUNT)

        self.assertEqual(stamp_should_be, TestNetTransaction.stamp_tx(AMOUNT))

    def test_vote_tx_build(self):
        CANDIDATE = 'jason'

        vote_should_be = (TestNetTransaction.VOTE, CANDIDATE)

        self.assertEqual(vote_should_be, TestNetTransaction.vote_tx(CANDIDATE))

    def test_sign_std_tx(self):
        (s, v) = ED25519Wallet.new()

        TO = 'jason'
        AMOUNT = '1001'

        tx = TestNetTransaction.standard_tx(TO, AMOUNT)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=TwofishPOW)
        transaction_factory.build(tx, s, complete=True, use_stamp=True)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        self.assertTrue(transaction_factory.verify_tx(full_tx, v, sig))

    def test_sign_std_tx_pow(self):
        (s, v) = ED25519Wallet.new()

        TO = 'jason'
        AMOUNT = '1001'

        tx = TestNetTransaction.standard_tx(TO, AMOUNT)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=TwofishPOW)
        transaction_factory.build(tx, s, complete=True, use_stamp=False)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        proof = full_tx['metadata']['proof']

        self.assertTrue(TwofishPOW.check(str(full_tx['payload']).encode(), proof[0]))
        self.assertTrue(transaction_factory.verify_tx(full_tx, v, sig))

    def test_stamp_std_tx(self):
        (s, v) = ED25519Wallet.new()

        AMOUNT = '1000'

        tx = TestNetTransaction.stamp_tx(AMOUNT)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=TwofishPOW)
        transaction_factory.build(tx, s, complete=True, use_stamp=True)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        self.assertTrue(transaction_factory.verify_tx(full_tx, v, sig))

    def test_stamp_std_tx_pow(self):
        (s, v) = ED25519Wallet.new()

        AMOUNT = '1000'

        tx = TestNetTransaction.stamp_tx(AMOUNT)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=TwofishPOW)
        transaction_factory.build(tx, s, complete=True, use_stamp=False)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        proof = full_tx['metadata']['proof']

        self.assertTrue(TwofishPOW.check(str(full_tx['payload']).encode(), proof[0]))
        self.assertTrue(transaction_factory.verify_tx(full_tx, v, sig))

    def test_stamp_vote_tx(self):
        (s, v) = ED25519Wallet.new()

        CANDIDATE = 'jason'

        tx = TestNetTransaction.vote_tx(CANDIDATE)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=TwofishPOW)
        transaction_factory.build(tx, s, complete=True, use_stamp=True)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        self.assertTrue(transaction_factory.verify_tx(full_tx, v, sig))

    def test_stamp_std_tx_pow(self):
        (s, v) = ED25519Wallet.new()

        CANDIDATE = 'jason'

        tx = TestNetTransaction.vote_tx(CANDIDATE)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=TwofishPOW)
        transaction_factory.build(tx, s, complete=True, use_stamp=False)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        proof = full_tx['metadata']['proof']

        self.assertTrue(TwofishPOW.check(str(full_tx['payload']).encode(), proof[0]))
        self.assertTrue(transaction_factory.verify_tx(full_tx, v, sig))