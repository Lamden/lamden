from unittest import TestCase
from cilantro.messages import MerkleSignature, BlockContender
from cilantro.protocol.wallets import ED25519Wallet


TIMESTAMP = 'now'

class BlockContenderTest(TestCase):

    def _create_merkle_sig(self, msg: bytes):
        """
        Helper method to create a MerkleSignature and wallet keys
        :return: A tuple container (MerkleSignature, signing_key, verifying_key)
        """
        assert type(msg) == bytes, "Must pass in bytes"

        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)
        ms = MerkleSignature.create(sig_hex=signature, timestamp=TIMESTAMP, sender=vk)

        return ms, sk, vk

    def test_creation(self):
        """
        Tests that a created BlockContender has the expected properties
        """
        # TODO -- implement

        msg = b'DEADBEEF'
        nodes = [1, 2]

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        signatures = [sig1, sig2]

        bc = BlockContender.create(signatures, nodes)

        # TODO: assert bc.signatures = signature (they are lists so you will have to iterate over them and compare elements)
        # TODO: would be wise to implement __eq__ in MerkleSignature to you can compare objects hella ez

        # TODO: assert bc.nodes = nodes (again be weary of comparing lists)

    def test_deserialize_invalid(self):
        """
        Tests that attempting to create a BlockContender from bad binary throws an assertion
        """
        # TODO implement

        # (see test_deserialization_invalid in merk sig tests for example on how to do these)

        # TODO: test that creating a BlockContender with bad json throws an error

        # TODO: tests creating a BlockContender with valid json but missing fields ('signature' or 'nodes' field missing) throws an error

        # TODO: tests for faile when creating a BlockContender with valid json and valid fields,
        # but _data[BlockContender.SIGS] is not a list of MerkleSignature binaries
        # (i.e. if _data[BlockContender.SIGS] is a list of random garbage binary strings, an error should be thrown when trying
        # to create the BlockContender from binary because the signature cannot be deserialized into MerkleSignatures)

    def test_deserialize(self):
        """
        Tests that the same object is recovered when serialized and deserialized
        """
        # TODO implement

        # Create a BlockContender object
        # Serialize it
        # Create another one from the first one's binary
        # Compare .signatures and .nodes (again be weary of comparing lists)