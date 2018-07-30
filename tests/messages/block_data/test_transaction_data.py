import unittest
from unittest import TestCase
from cilantro.messages import TransactionReply, TransactionRequest, ContractTransactionBuilder
from cilantro.protocol.wallet import Wallet
from cilantro.protocol.structures import MerkleTree
from cilantro.utils import Hasher


class TestTransactionRequest(TestCase):

    def test_creation(self):
        """
        Tests that a created block data request has the expected properties
        """
        tx_hashes = ['A' * 64, 'B' * 64, 'C' * 64]
        bdr = TransactionRequest.create(tx_hashes)
        self.assertEqual(bdr.tx_hashes, tx_hashes)

    def test_creation_fail(self):
        """
        Tests that a created block data request has the expected properties
        """
        tx_hashes = ['A' * 64, 'B' * 64, 'C' * 67]
        with self.assertRaises(Exception) as e:
            bdr = TransactionRequest.create(tx_hashes)

    def test_serialization(self):
        """
        Tests that a message successfully serializes and deserializes. The deserialized object should have the same
        properties as the original one before it was serialized.
        """
        tx_hashes = ['A' * 64, 'B' * 64, 'C' * 64]
        original = TransactionRequest.create(tx_hashes)
        original_binary = original.serialize()
        clone = TransactionRequest.from_bytes(original_binary)  # deserialize byte object

        self.assertEqual(original.tx_hashes, clone.tx_hashes)


class TestTransactionReply(TestCase):
    def test_creation(self):
        """
        Tests that a created block data reply has the expected properties
        """
        sk = Wallet.new()[0]
        contracts = [
            ContractTransactionBuilder.create_contract_tx(sk, code_str) \
            for code_str in ['some random binary', 'some deterministic binary', 'While True: self.eatAss()']
        ]
        tx_binaries = [c.serialize() for c in contracts]
        bdr = TransactionReply.create(tx_binaries)
        self.assertEqual(contracts, bdr.transactions)

    def test_serialization(self):
        """
        Tests that a created block data reply successfully serializes and deserializes. The deserialized object should
        have the same properties as the original one before it was serialized.
        """
        tx_binaries = [b'some random binary']
        with self.assertRaises(Exception) as e:
            original = TransactionReply.create(tx_binaries)

    def test_validate_matches_request(self):
        """
        Tests that a created block data reply has the expected properties
        """
        sk = Wallet.new()[0]
        code_strs = ['some random binary', 'some deterministic binary', 'While True: self.eatAss()']
        contracts = [
            ContractTransactionBuilder.create_contract_tx(sk, code_str) \
            for code_str in code_strs
        ]
        tx_binaries = [c.serialize() for c in contracts]



        tx_hashes = [Hasher.hash(cs) for cs in tx_binaries]
        bdr_req = TransactionRequest.create(tx_hashes)

        bdr_rep = TransactionReply.create(tx_binaries)
        assert bdr_rep.validate_matches_request(bdr_req), 'No match'

    def test_validate_matches_request_no_match(self):
        """
        Tests that a created block data reply has the expected properties
        """
        sk = Wallet.new()[0]
        code_strs = ['some random binary', 'some deterministic binary', 'While True: self.eatAss()']
        contracts = [
            ContractTransactionBuilder.create_contract_tx(sk, code_str) \
            for code_str in code_strs
        ]
        tx_binaries = [c.serialize() for c in contracts]

        tx_hashes = [Hasher.hash(cs+b'bbb') for cs in tx_binaries]
        bdr_req = TransactionRequest.create(tx_hashes)

        bdr_rep = TransactionReply.create(tx_binaries)
        assert not bdr_rep.validate_matches_request(bdr_req)

    def test_validate_matches_request_wrong_length(self):
        """
        Tests that a created block data reply has the expected properties
        """
        sk = Wallet.new()[0]
        code_strs = ['some random binary', 'some deterministic binary', 'While True: self.eatAss()']
        contracts = [
            ContractTransactionBuilder.create_contract_tx(sk, code_str) \
            for code_str in code_strs
        ]
        tx_binaries = [c.serialize() for c in contracts]

        tx_hashes = [Hasher.hash(cs+b'bbb') for cs in tx_binaries][:1]
        bdr_req = TransactionRequest.create(tx_hashes)

        bdr_rep = TransactionReply.create(tx_binaries)
        assert not bdr_rep.validate_matches_request(bdr_req)

    def test_serialization(self):
        """
        Tests that a message successfully serializes and deserializes. The deserialized object should have the same
        properties as the original one before it was serialized.
        """
        sk = Wallet.new()[0]
        code_strs = ['some random binary', 'some deterministic binary', 'While True: self.eatAss()']
        contracts = [
            ContractTransactionBuilder.create_contract_tx(sk, code_str) \
            for code_str in code_strs
        ]
        tx_binaries = [c.serialize() for c in contracts]
        original = TransactionReply.create(tx_binaries)
        original_binary = original.serialize()
        clone = TransactionReply.from_bytes(original_binary)  # deserialize byte object

        self.assertEqual(original.transactions, clone.transactions)

if __name__ == '__main__':
    unittest.main()
