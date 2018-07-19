from unittest import TestCase
from cilantro.messages import TransactionReply, TransactionRequest
from cilantro.protocol.structures import MerkleTree


class TestTransactionRequest(TestCase):
# TODO conform to new API and implement
    def test_creation(self):
        """
        Tests that a created block data request has the expected properties
        """
        tx_hash = 'A' * 64
        bdr = TransactionRequest.create(tx_hash)

        self.assertEqual(bdr.tx_hash, tx_hash)

    def test_serialization(self):
        """
        Tests that a message successfully serializes and deserializes. The deserialized object should have the same
        properties as the original one before it was serialized.
        """
        tx_hash = 'A' * 64
        original = TransactionRequest.create(tx_hash)
        original_binary = original.serialize()
        clone = TransactionRequest.from_bytes(original_binary)  # deserialize byte object

        self.assertEqual(original.tx_hash, clone.tx_hash)


class TestTransactionReply(TestCase):
# TODO conform to new API and implement
    def test_creation(self):
        """
        Tests that a created block data reply has the expected properties
        """
        tx_binary = b'some random binary'
        bdr = TransactionReply.create(tx_binary)

        self.assertEqual(tx_binary, bdr.raw_tx)
        self.assertEqual(bdr.tx_hash, MerkleTree.hash(tx_binary))

    def test_serialization(self):
        """
        Tests that a created block data reply successfully serializes and deserializes. The deserialized object should
        have the same properties as the original one before it was serialized.
        """
        tx_binary = b'some random binary'
        original = TransactionReply.create(tx_binary)
        original_binary = original.serialize()

        clone = TransactionReply.from_bytes(original_binary)  # deserialize object

        # Assert the original and new one are equal using:
        self.assertEqual(original.raw_tx, clone.raw_tx)
        self.assertEqual(original.tx_hash, clone.tx_hash)

