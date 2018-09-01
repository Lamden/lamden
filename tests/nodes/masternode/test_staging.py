from unittest import TestCase
from unittest.mock import MagicMock, patch
from cilantro.nodes.masternode.masternode import MNBootState, MNRunState, MNStagingState
from cilantro.protocol.states.statemachine import StateTransition
from cilantro.protocol.states.state import EmptyState
from cilantro.messages.transaction.base import TransactionBase
from collections import deque
import asyncio


class TestMasterNodeStagingState(TestCase):

    @classmethod
    def setUpClass(cls):
        # Create a new event loop for this test suite
        asyncio.set_event_loop(asyncio.new_event_loop())

    # Deprecated b/c Web server does this logic now
    # def test_handle_tx_adds_to_queue(self):
    #     mock_queue = MagicMock(spec=deque)
    #     mock_sm = MagicMock(tx_queue=mock_queue)
    #     state = MNStagingState(state_machine=mock_sm)
    #     state.call_transition_handler(trans_type=StateTransition.ENTER, state=MNBootState)
    #
    #     mock_tx = MagicMock(spec=TransactionBase)
    #
    #     state.handle_tx(mock_tx)
    #
    #     mock_queue.append.assert_called_with(mock_tx)

    def test_latest_block_request_adds_to_ready_delegates(self):
        """
        Tests that getting a BlockMetaDataRequest for the latest block hash adds
        :return:
        """
        # TODO implement ... figure out how to easily mock request and reply envelopes
        pass

    def test_staging_correctly_exits(self):
        """
        Tests that staging state correctly exists when enough TESTNET_DELEGATES are ready
        """
        # TODO implement
        pass
