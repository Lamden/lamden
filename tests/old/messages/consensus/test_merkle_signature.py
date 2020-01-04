from unittest import TestCase
from cilantro_ee.crypto import wallet
from cilantro_ee.messages.consensus.merkle_signature import build_test_merkle_sig, MerkleSignature
import json


class TestMerkleSignature(TestCase):

    def test_valid_creation(self):
        """
        Tests that a MerkleSignature created with some argument has the expected properties
        """
        msg = b'this is a pretend merkle tree hash'
        timestamp = 'now'
        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)
        ms = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk)

        self.assertEqual(ms.signature, signature)
        self.assertEqual(ms.timestamp, timestamp)
        self.assertEqual(ms.sender, vk)

    def test_invalid_signature_nonhex(self):
        """
        Tests that an error is raised during validation if an invalid signature is passed (nonhex, or length != 128)
        """
        msg = b'this is a pretend merkle tree hash'
        timestamp = 'now'
        sk, vk = wallet.new()

        # Test nonhex signature (but valid length)
        sig = ''.join(('X' for _ in range(128)))
        nonhex = MerkleSignature.create(sig_hex=sig, timestamp=timestamp, sender=vk, validate=False)
        self.assertRaises(Exception, nonhex.validate)

    def test_invalid_signature_bad_length(self):
        # Test signature incorrect length (but valid hex)
        sk, vk = wallet.new()
        timestamp = 'now'
        sig = ''.join(('A' for _ in range(100)))
        wrong_len = MerkleSignature.create(sig_hex=sig, timestamp=timestamp, sender=vk, validate=False)
        self.assertRaises(Exception, wrong_len.validate)

    def test_validate_catches_bad_sig(self):
        # test that validate is called by default and throws an exception with bad sig
        sk, vk = wallet.new()
        sig = ''.join(('X' for _ in range(128)))
        timestamp = 'now'

        self.assertRaises(Exception, MerkleSignature.create, sig_hex=sig, timestamp=timestamp, sender=vk)

    def test_invalid_sender_wrong_sender(self):
        """
        Tests that an error is raised during creation if an invalid sender field is passed in. A sender should be a
        64 character hex string verifying key.
        """
        # Test an error is thrown when MerkleSignature created with a sender that is not the correct public key
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)

        timestamp = 'now'
        vk_bad = wallet.new()[1]  # different verifying (public) key
        bad_public_key = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk_bad)
        self.assertRaises(Exception, bad_public_key)

    def test_valid_sender(self):
        # Confirm no error when correct public key is used
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)

        timestamp = 'now'
        MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk)  # no error thrown

    def test_invalid_sender_bad_hash(self):
        # Test an error is thrown when created with a sender of not valid hash
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)

        timestamp = 'now'
        vk_bad_hash = ''.join('Z' for _ in range(64))  # verifying (public) key with bad hash
        self.assertRaises(Exception, MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk_bad_hash,
                                                            validate=False))

    def test_invalid_sender_bad_pk_length(self):
        # Test an error is thrown when created with a sender of invalid length (not 64)
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)

        timestamp = 'now'
        vk_bad_length = ''.join('e' for _ in range(75))  # verifying (public) key with bad length

        self.assertRaises(Exception, MerkleSignature.create(sig_hex=signature, timestamp=timestamp,
                                                            sender=vk_bad_length, validate=False))

    def test_invalid_timestamp(self):
        """
        Test that if the timestamp field is not formatted as expected an error will be thrown
        """
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)

        timestamp = 99
        self.assertRaises(TypeError, MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk))

    def test_deserialization_invalid_json(self):
        """
        Tests that attempting to deserialize a MerkleSignature from a bad binary (not json, not valid fields, ect) throws
        as error
        """
        # Test bad (invalid) JSON
        bad_json = b'lololololol()**[][]XXX-----!!!!!'
        self.assertRaises(json.decoder.JSONDecodeError, MerkleSignature.from_bytes, bad_json)

    def test_deserialization_missing_fields(self):
        # Test valid json but missing fields
        sig = ''.join(('A' for _ in range(128)))
        d = {MerkleSignature.SIG: sig, MerkleSignature.TS: 'now'}
        binary = json.dumps(d).encode()
        self.assertRaises(AssertionError, MerkleSignature.from_bytes, binary)

    def test_deserialization_bad_sk_length(self):
        # Test valid json but signature (private key) is of the wrong length
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        sig = ''.join(('A' for _ in range(100)))

        d = {MerkleSignature.SIG: sig, MerkleSignature.TS: 'now', MerkleSignature.SENDER: vk}
        binary = json.dumps(d).encode()
        self.assertRaises(Exception, MerkleSignature.from_bytes, binary)

    def test_deserialization_bad_sk_hex(self):
        # Test valid json but signature (private key) not proper hex
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        sig = ''.join(('Z' for _ in range(128)))

        d = {MerkleSignature.SIG: sig, MerkleSignature.TS: 'now', MerkleSignature.SENDER: vk}
        binary = json.dumps(d).encode()
        self.assertRaises(Exception, MerkleSignature.from_bytes, binary)

    def test_deserialization_valid_json(self):
        # Test valid json throws no errors
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)

        d = {MerkleSignature.SIG: signature, MerkleSignature.TS: 'now', MerkleSignature.SENDER: vk}
        binary = json.dumps(d).encode()
        MerkleSignature.from_bytes(binary)

    def test_serialization(self):
        """
        Tests that a created block data reply successfully serializes and deserializes. The deserialized object should
        have the same properties as the original one before it was serialized.
        """
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)

        timestamp = 'now'
        valid_merkle_sig = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk)

        valid_merkle_sig_serialized = valid_merkle_sig.serialize()

        clone = MerkleSignature.from_bytes(valid_merkle_sig_serialized)

        self.assertEqual(valid_merkle_sig.signature, clone.signature)
        self.assertEqual(valid_merkle_sig.timestamp, clone.timestamp)
        self.assertEqual(valid_merkle_sig.sender, clone.sender)

    def test_verify_valid_ms(self):
        """
        Tests that MerkleSignature.verify(...) returns true given a proper msg and vk
        """
        # Test merkle tree verify() validates correct verifying (public) keys
        msg = b'this is a pretend merkle tree hash'
        timestamp = 'now'
        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)
        ms = MerkleSignature.create(sig_hex=signature, timestamp=timestamp, sender=vk)

        self.assertTrue(ms.verify(msg))

    def test_build_test_merkle_sig(self):
        """
        Tests build_test_contender. This is used exclusively unit tests, so we basically just want to make sure it
        doesn't blow up here first.
        """
        sig = build_test_merkle_sig()

    def test_create_from_payload(self):
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        sig = MerkleSignature.create_from_payload(signing_key=sk, payload=msg)
        self.assertTrue(sig.verify(msg))

    def test_create_from_payload_cloned(self):
        msg = b'this is a pretend merkle tree hash'
        sk, vk = wallet.new()
        sig = MerkleSignature.create_from_payload(signing_key=sk, payload=msg)
        clone = MerkleSignature.from_bytes(sig.serialize())
        self.assertTrue(clone.verify(msg))
