import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch
from cilantro.nodes.masternode.masternode import MNBootState, MNRunState, MNStagingState
from cilantro.protocol.states.statemachine import StateTransition
from cilantro.protocol.states.state import EmptyState
from cilantro.utils.lprocess import LProcess

from cilantro.messages.transaction.container import TransactionContainer
from cilantro.logger.base import overwrite_logger_level
from cilantro.utils.test.god import God
import os, time, subprocess

overwrite_logger_level(10001)

class TestWebserverPerformance(TestCase):

    def test_server_perf(self):
        ip = '136.25.1.11'
        mock_sm = MagicMock(ip=ip)

        mock_composer = MagicMock()
        mock_sm.composer = mock_composer

        state = MNBootState(state_machine=mock_sm)

        state.call_transition_handler(trans_type=StateTransition.ENTER, state=EmptyState)

        subprocess.run('ab -k -c 50 -n 10000 -p post_data 0.0.0.0:8080/'.split(' '))

if __name__ == '__main__':
    unittest.main()
