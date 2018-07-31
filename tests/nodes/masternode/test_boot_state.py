from unittest import TestCase
from unittest.mock import MagicMock, patch
from cilantro.nodes.masternode.masternode import MNBootState, MNRunState
from cilantro.protocol.states.statemachine import StateTransition
from cilantro.protocol.states.state import EmptyState

class TestMasterNodeBootState(TestCase):

    def test_entry_adds_pub(self):
        """
        Tests that boot state adds a publisher socket on the Node's own URL on state entry
        """
        ip = '136.25.1.11'
        mock_sm = MagicMock(ip=ip)

        mock_composer = MagicMock()
        mock_sm.composer = mock_composer

        state = MNBootState(state_machine=mock_sm)

        state.call_transition_handler(trans_type=StateTransition.ENTER, state=EmptyState)

        mock_composer.add_pub.assert_called_with(ip=ip)

    def test_entry_adds_router(self):
        """
        Tests that boot state adds a router socket on the Node's own URL on state entry
        """
        ip = '136.25.1.11'
        mock_sm = MagicMock(ip=ip)

        mock_composer = MagicMock()
        mock_sm.composer = mock_composer

        state = MNBootState(state_machine=mock_sm)

        state.call_transition_handler(trans_type=StateTransition.ENTER, state=EmptyState)

        mock_composer.add_router.assert_called_with(ip=ip)

    def test_entry_transitions_to_run(self):
        """
        Tests that boot state transitions to run state once setup has been done
        """
        mock_sm = MagicMock()
        state = MNBootState(state_machine=mock_sm)

        state.call_transition_handler(trans_type=StateTransition.ENTER, state=EmptyState)

        mock_sm.transition.assert_called_with(MNRunState)
