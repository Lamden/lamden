from unittest import TestCase
from cilantro.transactions import TestNetTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
import secrets
import hashlib
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
        payload_binary = TestNetTransaction.SERIALIZER.serialize(full_tx['payload'])

        proof = full_tx['metadata']['proof']
        self.assertTrue(SHA3POW.check(payload_binary, proof[0]))
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
        payload_binary = TestNetTransaction.SERIALIZER.serialize(full_tx['payload'])

        self.assertTrue(SHA3POW.check(payload_binary, proof[0]))
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
        payload_binary = TestNetTransaction.SERIALIZER.serialize(full_tx['payload'])

        self.assertTrue(SHA3POW.check(payload_binary, proof[0]))
        self.assertTrue(TestNetTransaction.verify_tx(full_tx, v, sig, ED25519Wallet, SHA3POW))

    def test_swap_std_tx_pow(self):
        (s, v) = ED25519Wallet.new()
        RECIPIENT = 'davis'
        AMOUNT = '100'

        secret = secrets.token_hex(16)
        hash = hashlib.sha3_256()
        hash.update(bytes.fromhex(secret))

        HASH_LOCK = hash.digest().hex()
        UNIX_EXPIRATION = '1000'

        tx = TestNetTransaction.swap_tx(v, RECIPIENT, AMOUNT, HASH_LOCK, UNIX_EXPIRATION)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=SHA3POW)
        transaction_factory.build(tx, s, complete=True, use_stamp=False)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        proof = full_tx['metadata']['proof']
        payload_binary = TestNetTransaction.SERIALIZER.serialize(full_tx['payload'])

        self.assertTrue(SHA3POW.check(payload_binary, proof[0]))
        self.assertTrue(TestNetTransaction.verify_tx(full_tx, v, sig, ED25519Wallet, SHA3POW))

    def test_redeem_std_tx_pow(self):
        (s, v) = ED25519Wallet.new()
        SECRET = secrets.token_hex(16)

        tx = TestNetTransaction.redeem_tx(v, SECRET)

        transaction_factory = TestNetTransaction(wallet=ED25519Wallet, proof=SHA3POW)
        transaction_factory.build(tx, s, complete=True, use_stamp=False)

        full_tx = transaction_factory.payload
        sig = full_tx['metadata']['signature']

        proof = full_tx['metadata']['proof']
        payload_binary = TestNetTransaction.SERIALIZER.serialize(full_tx['payload'])

        self.assertTrue(SHA3POW.check(payload_binary, proof[0]))
        self.assertTrue(TestNetTransaction.verify_tx(full_tx, v, sig, ED25519Wallet, SHA3POW))

    def test_from_dict_std_tx(self):
        tx_dict = {
            "metadata": {
                "proof": "e5685adafe831b6dbb2fd4fb580138b3",
                "signature": "028570e317407ab675bce76e4f5001e5e38b29f98cb65bf978135c30ca76a4e28e2f1f580ab8a6f35d1a4315d488f2ff0afe92dd7332cc89bb9bc298df87800b"
            },
            "payload": {
                "amount": "4",
                "from": "260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f",
                "to": "f7947784333851ec363231ade84ca63b21d03e575b1919f4042959bcd3c89b5f",
                "type": TestNetTransaction.TX
            }
        }

        expected_payload = (TestNetTransaction.TX, tx_dict['payload']['from'],
                            tx_dict['payload']['to'], tx_dict['payload']['amount'])
        tx = TestNetTransaction.from_dict(tx_dict)
        self.assertEqual(expected_payload, tx.payload['payload'])

    def test_from_dict_stamp_tx(self):
        tx_dict = {
            "metadata": {
                "proof": 'e5685adafe831b6dbb2fd4fb580138b3',
                "signature": "028570e317407ab675bce76e4f5001e5e38b29f98cb65bf978135c30ca76a4e28e2f1f580ab8a6f35d1a4315d488f2ff0afe92dd7332cc89bb9bc298df87800b"
            },
            "payload": {
                "amount": "4",
                "from": "260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f",
                "type": TestNetTransaction.STAMP
            }
        }

        expected_payload = (TestNetTransaction.STAMP, tx_dict['payload']['from'], tx_dict['payload']['amount'])
        tx = TestNetTransaction.from_dict(tx_dict)
        self.assertEqual(expected_payload, tx.payload['payload'])


    def test_from_dict_vote(self):
        tx_dict = {
            "metadata": {
                "proof": 'e5685adafe831b6dbb2fd4fb580138b3',
                "signature": "028570e317407ab675bce76e4f5001e5e38b29f98cb65bf978135c30ca76a4e28e2f1f580ab8a6f35d1a4315d488f2ff0afe92dd7332cc89bb9bc298df87800b"
            },
            "payload": {
                "from": "f7947784333851ec363231ade84ca63b21d03e575b1919f4042959bcd3c89b5f",
                "to": "260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f",
                "type": TestNetTransaction.VOTE
            }
        }
        expected_payload = (TestNetTransaction.VOTE, tx_dict['payload']['from'], tx_dict['payload']['to'])
        tx = TestNetTransaction.from_dict(tx_dict)
        self.assertEqual(expected_payload, tx.payload['payload'])

    def test_from_dict_swap(self):
        tx_dict = {
            "metadata": {
                "proof": 'e5685adafe831b6dbb2fd4fb580138b3',
                "signature": "028570e317407ab675bce76e4f5001e5e38b29f98cb65bf978135c30ca76a4e28e2f1f580ab8a6f35d1a4315d488f2ff0afe92dd7332cc89bb9bc298df87800b"
            },
            "payload": {
                "from": "f7947784333851ec363231ade84ca63b21d03e575b1919f4042959bcd3c89b5f",
                "to": "260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f",
                "amount": "100",
                "hash_lock": "abcdef12345678",
                "unix_expiration": "123456789",
                "type": TestNetTransaction.SWAP
            }
        }

        tx = TestNetTransaction.from_dict(tx_dict)
        expected_payload = (TestNetTransaction.SWAP,
                            tx_dict['payload']['from'],
                            tx_dict['payload']['to'],
                            tx_dict['payload']['amount'],
                            tx_dict['payload']['hash_lock'],
                            tx_dict['payload']['unix_expiration'])

        self.assertEqual(expected_payload, tx.payload['payload'])

    def test_from_dict_redeem(self):
        tx_dict = {
            "metadata": {
                "proof": 'e5685adafe831b6dbb2fd4fb580138b3',
                "signature": "028570e317407ab675bce76e4f5001e5e38b29f98cb65bf978135c30ca76a4e28e2f1f580ab8a6f35d1a4315d488f2ff0afe92dd7332cc89bb9bc298df87800b"
            },
            "payload": {
                "secret": "1234567890",
                "from": "260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f",
                "type": TestNetTransaction.REDEEM
            }
        }

        tx = TestNetTransaction.from_dict(tx_dict)
        expected_payload = (TestNetTransaction.REDEEM,
                            tx_dict['payload']['from'],
                            tx_dict['payload']['secret'])

        self.assertEqual(expected_payload, tx.payload['payload'])

    def test_from_dict_invalid_type(self):
        tx_dict = {
            "metadata": {
                "proof": 'e5685adafe831b6dbb2fd4fb580138b3',
                "signature": "028570e317407ab675bce76e4f5001e5e38b29f98cb65bf978135c30ca76a4e28e2f1f580ab8a6f35d1a4315d488f2ff0afe92dd7332cc89bb9bc298df87800b"
            },
            "payload": {
                "secret": "1234567890",
                "from": "260e707fa8e835f2df68f3548230beedcfc51c54b486c7224abeb8c7bd0d0d8f",
                "type": "xxx"
            }
        }

        self.assertRaises(Exception, TestNetTransaction.from_dict, tx_dict)