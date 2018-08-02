from unittest import TestCase
from unittest.mock import MagicMock, patch
from cilantro.nodes.masternode.masternode import MNBootState, MNRunState
from cilantro.protocol.states.state import StateTransition, StateInput
from cilantro.messages.consensus.block_contender import BlockContender, build_test_contender


class TestMasterNodeRunState(TestCase):

    def test_input_block_contender(self):
        """
        Tests that receiving a block contender in RunState pushes the SM into NewBlockState
        """
        mock_sm = MagicMock()
        bc = build_test_contender()

        state = MNRunState(state_machine=mock_sm)

        state.call_input_handler(bc, StateInput.REQUEST)

        mock_sm.transition.assert_called_with('MNNewBlockState', block=bc)

