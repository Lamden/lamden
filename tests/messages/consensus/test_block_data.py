from unittest import TestCase
from cilantro.messages import BlockDataReply, BlockDataRequest
from cilantro.protocol.structures import MerkleTree


class TestBlockDataRequest(TestCase):

    def test_creation(self):
        """
        Tests that a created block data request has the expected properties
        """
        tx_hash = b'DEADBEEF1337'
        bdr = BlockDataRequest.create(tx_hash)

        self.assertEqual(bdr.tx_hash, tx_hash)

    def test_serialization(self):
        """
        Tests that a message successfully serializes and deserializes. The deserialized object should have the same
        properties as the original one before it was serialized.
        """
        tx_hash = b'DEADBEEF1337'
        original = BlockDataRequest.create(tx_hash)
        original_binary = original.serialize()
        clone = BlockDataRequest.from_bytes(original_binary)

        self.assertEqual(original.tx_hash, clone.tx_hash)


class TestBlockDataReply(TestCase):

    def test_creation(self):
        """
        Tests that a created block data reply has the expected properties
        """

        # TODO -- implement

        tx_binary = b'some random binary'
        # Create a BlockDataReply (called, say, 'bdr') with tx_binary

        # Assert that the bdr.raw_tx equals tx_binary
        # Assert bdr.tx_hash equals MerkleTree.hash(tx_binary)

    def test_serialization(self):
        """
        Tests that a created block data reply successfully serializes and deserializes. The deserialized object should
        have the same properties as the original one before it was serialized.
        """

        # TODO -- implement

        # Create BlockDataReply with some tx_binary

        # Create a new BlockDataReply by serializing the original and calling BlockDataReply.from_bytes(...)

        # Assert the original and new one are equal using:
        # self.assertEqual(original.raw_tx, new.raw_tx)
        # self.assertEqual(original.tx_hash, new.tx_hash)

