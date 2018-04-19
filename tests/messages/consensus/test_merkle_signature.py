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

        # note, you could also do these checks like this:
        # self.assertRaises(Exception, MerkleSignature.create, sig_hex=sig, timestamp=timestamp, sender=vk)
        # i.e. testing that create calls validate, which should raise an exception.

    def test_invalid_sender(self):
        """
        Tests that an error is raised during creation if an invalid sender field is passed in. A sender should be a
        64 character hex string verifying key.
        """

        # TODO -- implement

        # Test an error is thrown when MerkleSignature created with a sender that is invalid hex

        # Test an error is thrown when created with a sender of invalid length (not 64)

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

        # TODO -- test an exception is thrown when creating with json with all fields present, but some fields invalid
        # ie. a dict with all 3 keys MerkleSignature.SIG, MerkleSignature.TS, and MerkleSignature.SENDER, but one or
        # all of these fields have invalid values (like wrong length, not valid hex, whatever)

    def test_serialization(self):
        """
        Tests that a created block data reply successfully serializes and deserializes. The deserialized object should
        have the same properties as the original one before it was serialized.
        """

        # TODO -- implement

        # Create valid MerkleSignature object
        # Serialize it by calling .serialize() and create a clone from its binary by calling
        # MerkleSignature.from_bytes(...) passing in the binary you just got from .serialize()

        # Assert that the original and 'clone' have equal signature, timestamp, and sender properties (3 assertions)

    def test_verify(self):
        """
        Tests that MerkleSignature.verify(...) returns true given a proper msg and vk
        """
        msg = b'this is a pretend merkle tree hash'
        timestamp = 'now'
        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)
        ms = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk)


        # for these use self.assertTrue(expression) and use self.assertFalse(expression)

        # TODO -- assert that ms.verify(msg, vk) returns True

        # TODO -- assert that ms.verify(msg, vk') returns False for vk' != vk

        # TODO -- assert that ms.verify(msg, vk') returns False for invalid verifying key vk' (not hex or wrong length)
