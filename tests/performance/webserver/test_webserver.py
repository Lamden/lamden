import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch
from cilantro.nodes.masternode.masternode import MNBootState, MNRunState, MNStagingState
from cilantro.protocol.states.statemachine import StateTransition
from cilantro.protocol.states.state import EmptyState
from cilantro.utils.lprocess import LProcess

import cilantro
from cilantro.messages.transaction.container import TransactionContainer
from cilantro.logger.base import overwrite_logger_level
from cilantro.utils.test.god import God
import os, time, subprocess

overwrite_logger_level(10001)

class TestWebserverPerformance(TestCase):

    def test_server_perf(self):
        os.system('python3 {}/nodes/masternode/webserver.py &'.format(cilantro.__path__[0]))
        time.sleep(2)
        subprocess.run('ab -k -c 50 -n 10000 -p post_data 0.0.0.0:8080/'.split(' '))

if __name__ == '__main__':
    unittest.main()
