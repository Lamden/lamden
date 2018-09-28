from cilantro.logger.base import get_logger
from cilantro.constants.testnet import TESTNET_DELEGATES
from cilantro.nodes.delegate.block_manager import IPC_IP, IPC_PORT
from cilantro.nodes.delegate.sub_block_builder import SubBlockBuilder, SubBlockManager
from cilantro.utils import int_to_bytes
from cilantro.messages.transaction.batch import TransactionBatch
from cilantro.messages.base.base import MessageBase
from cilantro.messages.consensus.empty_sub_block_contender import EmptySubBlockContender

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
        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=TEST_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT,
                              num_sb_builders=4, total_sub_blocks=16, num_blocks=2)
        
        self.assertTrue(len(sbb.sb_managers) == 4)
        self.assertTrue(sbb.num_sb_per_block == 2)


    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.asyncio", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.SubBlockBuilder", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.SubBlockBuilder.run", autospec=True)
    def test_sub_msg_with_make_next_block_notification_calls_handle_ipc_msg(self, mock_run_method, mock_bm_asyncio,
                                                                            mock_sbb, mock_manager, mock_worker_asyncio):
        """
        Tests handle_ipc_msg correctly calls handle_new_block when a NewBlockNotification is received
        """

        sbb = SubBlockBuilder(ip=TEST_IP, signing_key=TEST_SK, sbb_index=0, ipc_ip=IPC_IP, ipc_port=IPC_PORT,
                              num_sb_builders=1, total_sub_blocks=1, num_blocks=1)
        
        self.assertTrue(len(sbb.sb_managers) == 1)
        self.assertTrue(sbb.num_sb_per_block == 1)

        # Mock Envelope.from_bytes to return a mock envelope of our choosing
        tx_list = []
        batch = TransactionBatch.create(tx_list)
        env = Envelope.create_from_message(message=batch, signing_key=sbb.signing_key,
                                            verifying_key=sbb.verifying_key)
        frames = [b'', env.serialize()]

        sbb._send_msg_over_ipc = MagicMock()
        sbb.handle_sub_msg(frames, 0)
        sbb._make_next_sub_block()
        sbb._send_msg_over_ipc.assert_called()

	# see what it was called with
        msg = sbb._send_msg_over_ipc.call_args[0][0]
        assert isinstance(msg, EmptySubBlockContender), "Must pass in an EmptySubBlockContender instance"
        # print("sbb._create_empty_sbc called with: {}".format(call_args))



if __name__ == "__main__":
    import unittest
    unittest.main()
