from unittest import TestCase
from unittest.mock import MagicMock, patch
from cilantro.nodes.masternode.masternode import MNBootState, MNRunState
from cilantro.protocol.statemachine import *
from cilantro.messages.consensus.block_contender import BlockContender, build_test_contender


class TestMasterNodeBootState(TestCase):

    def test_entry_from_boot_adds_server_task(self):
        """
        Tests that transitioning into RunState from BootState adds a server future to that state machine's tasks
        """
        tasks = []
        mock_sm = MagicMock(tasks=tasks)

        state = MNRunState(state_machine=mock_sm)

        num_tasks_before = len(tasks)
        state.call_transition_handler(trans_type=StateTransition.ENTER, state=MNBootState)
        num_tasks_after = len(tasks)

        self.assertTrue(num_tasks_after - num_tasks_before == 1)

    def test_input_block_contender(self):
        """
        Tests that receiving a block contender in RunState pushes the SM into NewBlockState
        """
        mock_sm = MagicMock()
        bc = build_test_contender()

        state = MNRunState(state_machine=mock_sm)

        state.call_input_handler(bc, StateInput.REQUEST)

        mock_sm.transition.assert_called_with('MNNewBlockState', block=bc)

