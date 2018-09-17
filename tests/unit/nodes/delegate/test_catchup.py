from cilantro.utils.hasher import Hasher
from cilantro.nodes.delegate.catchup import DelegateCatchupState, DelegateInterpretState
from cilantro.messages.block_data.transaction_data import TransactionRequest
from cilantro.messages.transaction import build_test_transaction
from cilantro.protocol.structures import MerkleTree
from cilantro.messages.block_data.block_metadata import BlockMetaData, BlockMetaDataRequest, BlockMetaDataReply
from unittest import TestCase
from unittest.mock import MagicMock


class TestCatchupState(TestCase):

    def test_handle_blockmeta_with_latest_transitions_to_interpret(self):
        """
        Tests that received a BlockMetaDataReply with no future block hashes sends the delegate to InterpretState
        """
        mock_sm = MagicMock()
        state = DelegateCatchupState(state_machine=mock_sm)
        mock_block_reply = MagicMock(spec=BlockMetaDataReply, block_metas=None)

        state.handle_blockmeta_reply(mock_block_reply)
        state.parent.transition.assert_called_with(DelegateInterpretState)

    def test_handle_blockmeta_with_new_blocks(self):
        mock_sm = MagicMock()
        state = DelegateCatchupState(state_machine=mock_sm)
        state._update_next_block = MagicMock()

        mock_block1 = MagicMock(spec=BlockMetaData)
        mock_block2 = MagicMock(spec=BlockMetaData)

        mock_block_reply = MagicMock(spec=BlockMetaDataReply, block_metas=[mock_block1, mock_block2])

        state.handle_blockmeta_reply(mock_block_reply)

        state.parent.transition.assert_not_called()  # If the reply has more blocks, we need to fetch these
        state._update_next_block.assert_called()  # _update_next_block() should be called
        self.assertEquals(state.new_blocks[-2:], [mock_block1, mock_block2])


    def test_new_block_notification_does_nothing(self):
        """
        Since we are already in CatchupState, receiving a new block notification should not do anything
        """
        # TODO implement
        pass

    def test_tx_reply_not_match_request(self):
        # TODO implement
        pass

    def test_tx_reply_not_match_merkle_leaves(self):
        # TODO implement
        pass

    def test_tx_reply_valid(self):
        # TODO implement
        pass
