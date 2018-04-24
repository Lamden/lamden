from unittest import TestCase
from cilantro.messages import MerkleSignature
from cilantro.protocol.wallets import ED25519Wallet
import json


class TestMerkleSignature(TestCase):

    def test_valid_creation(self):
        """
        Tests that a MerkleSignature created with some argument has the expected properties
        """
        msg = b'this is a pretend merkle tree hash'
        timestamp = 'now'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)
        ms = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk)

        self.assertEqual(ms.signature, signature)
        self.assertEqual(ms.timestamp, timestamp)
        self.assertEqual(ms.sender, vk)

    def test_invalid_signature(self):
        """
        Tests that an error is raised during validation if an invalid signature is passed (nonhex, or length != 128)
        """
        msg = b'this is a pretend merkle tree hash'
        timestamp = 'now'
        sk, vk = ED25519Wallet.new()

        # Test nonhex signature (but valid length)
        sig = ''.join(('X' for _ in range(128)))
        nonhex = MerkleSignature.create(sig_hex=sig, timestamp=timestamp, sender=vk, validate=False)
        self.assertRaises(Exception, nonhex.validate)

        # Test signature incorrect length (but valid hex)
        sig = ''.join(('A' for _ in range(100)))
        wrong_len = MerkleSignature.create(sig_hex=sig, timestamp=timestamp, sender=vk, validate=False)
        self.assertRaises(Exception, wrong_len.validate)

        # test that validate is called by default and throws an exception with bad sig
        sig = ''.join(('X' for _ in range(128)))
        self.assertRaises(Exception, MerkleSignature.create, sig_hex=sig, timestamp=timestamp, sender=vk)

    def test_invalid_sender(self):
        """
        Tests that an error is raised during creation if an invalid sender field is passed in. A sender should be a
        64 character hex string verifying key.
        """
        # Test an error is thrown when MerkleSignature created with a sender that is not the correct public key
        msg = b'this is a pretend merkle tree hash'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)

        timestamp = 'now'
        vk_bad = ED25519Wallet.new()[1]  # different verifying (public) key
        bad_public_key = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk_bad)
        self.assertRaises(Exception, bad_public_key)

        # Confirm no error when correct public key is used
        msg = b'this is a pretend merkle tree hash'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)

        timestamp = 'now'
        MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk)  # no error thrown

        # Test an error is thrown when created with a sender of not valid hash
        msg = b'this is a pretend merkle tree hash'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)

        timestamp = 'now'
        vk_bad_hash = ''.join('Z' for _ in range(64))  # verifying (public) key with bad hash
        self.assertRaises(Exception, MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk_bad_hash,
                                                            validate=False))

        # Test an error is thrown when created with a sender of invalid length (not 64)
        msg = b'this is a pretend merkle tree hash'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)

        timestamp = 'now'
        vk_bad_length = ''.join('e' for _ in range(75))  # verifying (public) key with bad length

        self.assertRaises(Exception, MerkleSignature.create(sig_hex=signature, timestamp=timestamp,
                                                            sender=vk_bad_length, validate=False))

    def test_invalid_timestamp(self):
        """
        Test that if the timestamp field is not formatted as expected an error will be thrown
        """
        msg = b'this is a pretend merkle tree hash'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)

        timestamp = 99
        self.assertRaises(TypeError, MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk))

    def test_deserialization_invalid(self):
        """
        Tests that attempting to deserialize a MerkleSignature from a bad binary (not json, not valid fields, ect) throws
        as error
        """
        # Test bad (invalid) JSON
        bad_json = b'lololololol()**[][]XXX-----!!!!!'
        self.assertRaises(json.decoder.JSONDecodeError, MerkleSignature.from_bytes, bad_json)

        # Test valid json but missing fields
        sig = ''.join(('A' for _ in range(128)))
        d = {MerkleSignature.SIG: sig, MerkleSignature.TS: 'now'}
        binary = json.dumps(d).encode()
        self.assertRaises(AssertionError, MerkleSignature.from_bytes, binary)

        # Test valid json but signature (private key) is of the wrong length
        msg = b'this is a pretend merkle tree hash'
        sk, vk = ED25519Wallet.new()
        sig = ''.join(('A' for _ in range(100)))

        d = {MerkleSignature.SIG: sig, MerkleSignature.TS: 'now', MerkleSignature.SENDER: vk}
        binary = json.dumps(d).encode()
        self.assertRaises(Exception, MerkleSignature.from_bytes, binary)

        # Test valid json but signature (private key) not proper hex
        msg = b'this is a pretend merkle tree hash'
        sk, vk = ED25519Wallet.new()
        sig = ''.join(('Z' for _ in range(128)))

        d = {MerkleSignature.SIG: sig, MerkleSignature.TS: 'now', MerkleSignature.SENDER: vk}
        binary = json.dumps(d).encode()
        self.assertRaises(Exception, MerkleSignature.from_bytes, binary)

        # Test valid json throws no errors
        msg = b'this is a pretend merkle tree hash'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)

        d = {MerkleSignature.SIG: signature, MerkleSignature.TS: 'now', MerkleSignature.SENDER: vk}
        binary = json.dumps(d).encode()
        MerkleSignature.from_bytes(binary)

    def test_serialization(self):
        """
        Tests that a created block data reply successfully serializes and deserializes. The deserialized object should
        have the same properties as the original one before it was serialized.
        """
        msg = b'this is a pretend merkle tree hash'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)

        timestamp = 'now'
        valid_merkle_sig = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk)

        valid_merkle_sig_serialized = valid_merkle_sig.serialize()

        clone = MerkleSignature.from_bytes(valid_merkle_sig_serialized)

        self.assertEqual(valid_merkle_sig.signature, clone.signature)
        self.assertEqual(valid_merkle_sig.timestamp, clone.timestamp)
        self.assertEqual(valid_merkle_sig.sender, clone.sender)

    def test_verify(self):
        return  # TODO fix
        """
        Tests that MerkleSignature.verify(...) returns true given a proper msg and vk
        """
        # Test merkle tree verify() validates correct verifying (public) keys
        msg = b'this is a pretend merkle tree hash'
        timestamp = 'now'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)
        ms = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk)

        self.assertTrue(ms.verify(signature, ms.sender))
        #
        # # Test merkle tree validation returns false for incorrect verifying (public) key
        # sk1, vk1 = ED25519Wallet.new()
        # signature = ED25519Wallet.sign(sk1, msg)
        # ms1 = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk1)
        #
        # self.assertFalse(ms.verify(msg, vk1))
        #
        # # TODO -- assert that ms.verify(msg, vk') returns False for invalid verifying key vk' (not hex or wrong length)
