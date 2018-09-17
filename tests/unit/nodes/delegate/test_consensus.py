from cilantro.nodes.delegate import DelegateConsensusState
from cilantro.utils.hasher import Hasher
from cilantro.messages.block_data.transaction_data import TransactionRequest
from cilantro.messages.transaction import build_test_transaction
from cilantro.protocol.structures import MerkleTree
from unittest import TestCase
from unittest.mock import MagicMock


class TestConsensus(TestCase):

    def test_queue_binary_correct(self):
        """
        Tests that self.parent.interpreter.queue_binary is indeed the binary data associated with valid transactions
        received by the delegate
        """

    def test_tx_request_replies_with_correct_data(self):
        """
        Tests that a delegate who receives a TransactionRequest in Consensus state replies with the correct data
        """
        mock_sm = MagicMock()
        state = DelegateConsensusState(mock_sm)

        # Build a merkle tree and attach it to the state
        tx_objects = [build_test_transaction() for _ in range(5)]
        tx_blobs = [tx.serialize() for tx in tx_objects]
        tx_hashes = [Hasher.hash(blob) for blob in tx_blobs]
        merkle_tree = MerkleTree.from_raw_transactions(tx_blobs)

        state.merkle = merkle_tree

        # Build a TransactionRequest for a few of these transactions
        requested_hashes = tx_hashes[1:4]
        expected_blobs = tx_blobs[1:4]
        request = TransactionRequest.create(transaction_hashes=requested_hashes)

        # Finally, ensure the reply is what we expect it to be
        reply = state.handle_tx_request(request)

        self.assertEquals(reply.raw_transactions, expected_blobs)