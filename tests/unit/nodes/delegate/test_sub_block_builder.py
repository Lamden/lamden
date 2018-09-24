from cilantro.logger.base import get_logger
from cilantro.constants.testnet import TESTNET_DELEGATES
from cilantro.nodes.delegate.block_manager import IPC_IP, IPC_PORT
from cilantro.nodes.delegate.sub_block_builder import SubBlockBuilder, SubBlockManager
from cilantro.utils import int_to_bytes

from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock

from cilantro.messages.envelope.envelope import Envelope

_log = get_logger("TestSubBlockBuilder")

TEST_IP = '127.0.0.1'
TEST_SK = TESTNET_DELEGATES[0]['sk']

class TestSubBlockBuilder(TestCase):

    # TODO we can probly DRY all this patching/setup code in a setup method or something
    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.SubBlockBuilder", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.asyncio", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.SubBlockBuilder.run", autospec=True)
    def test_create_sub_sockets(self, mock_run_method, mock_bm_asyncio, mock_sbb, mock_manager, mock_worker_asyncio):
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=TEST_SK, sbb_index=1, ipc_ip=IPC_IP, ipc_port=IPC_PORT,
                              num_sb_builders=4, total_sub_blocks=8, num_blocks=2)
        
        self.assertTrue(len(sbb.sb_managers) == 2)



if __name__ == "__main__":
    import unittest
    unittest.main()
