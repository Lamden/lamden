import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch
from cilantro_ee.nodes.masternode.masternode import MNBootState, MNRunState, MNStagingState
from cilantro_ee.protocol.states.statemachine import StateTransition
from cilantro_ee.protocol.states.state import EmptyState
from cilantro_ee.utils.lprocess import LProcess

import cilantro_ee
from cilantro_ee.messages.transaction.container import TransactionContainer
from cilantro_ee.logger.base import overwrite_logger_level
from cilantro_ee.utils.test.god import God
import os, time, subprocess

overwrite_logger_level(10001)

class TestWebserverPerformance(TestCase):

    def test_server_perf(self):
        os.system('python3 {}/nodes/masternode/webserver.py &'.format(cilantro_ee.__path__[0]))
        time.sleep(2)
        subprocess.run('ab -k -c 50 -n 10000 -p post_data 0.0.0.0:8080/'.split(' '))

if __name__ == '__main__':
    unittest.main()
