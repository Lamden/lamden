from cilantro.logger.base import get_logger
from cilantro.constants.testnet import TESTNET_MASTERNODES
from cilantro.nodes.masternode.block_aggregator import BlockAggregator

import unittest
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.sub_block_contender import SubBlockContender

TEST_IP = '127.0.0.1'
TEST_SK = TESTNET_MASTERNODES[0]['sk']

class TestBlockAggregator(TestCase):

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_build_task_list_creates_ipc_router(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        mock_manager = MagicMock()
        ba.manager = mock_manager

        mock_pub, mock_sub = MagicMock(), MagicMock()
        mock_manager.create_socket = MagicMock(side_effect=[mock_pub, mock_sub])

        mock_sub_handler_task = MagicMock()
        mock_sub.add_handler = MagicMock(return_value=mock_sub_handler_task)

        ba.build_task_list()

        print(ba.sub, ba.pub)

        # self.assertEqual(bm.ipc_router, mock_router)
        # mock_router.bind.assert_called_with(port=IPC_PORT, protocol='ipc', ip=bm.ipc_ip)
        # mock_router.add_handler.assert_called()
        # self.assertTrue(mock_router_handler_task in bm.tasks)

    # @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    # @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    # @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    # def test_handle_ipc_msg(self, mock_run_method, mock_bm_asyncio, mock_sbb, mock_manager, mock_worker_asyncio):
    #     bm = BlockManager(ip=TEST_IP, signing_key=TEST_SK)
    #     bm.manager = MagicMock()
    #     bm.ipc_router = MagicMock()
    #
    #     bm.build_task_list()
    #
    #     frames = [b'identity frame', b'this should be a real message binary']
    #
    #     bm.handle_ipc_msg(frames)
    #
    #     # TODO assert handle_ipc_msg does what expected
    #
    # @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    # @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    # @mock.patch("cilantro.nodes.delegate.block_manager.SubBlockBuilder", autospec=True)
    # @mock.patch("cilantro.nodes.delegate.block_manager.asyncio", autospec=True)
    # @mock.patch("cilantro.nodes.delegate.block_manager.BlockManager.run", autospec=True)
    # def test_sub_msg_with_new_block_notification_calls_handle_new_block(self, mock_run_method, mock_bm_asyncio,
    #                                                                     mock_sbb, mock_manager, mock_worker_asyncio):
    #     """
    #     Tests handle_sub_msg correctly calls handle_new_block when a NewBlockNotification is received
    #     """
    #     bm = BlockManager(ip=TEST_IP, signing_key=TEST_SK)
    #     bm.manager = MagicMock()
    #     bm.handle_new_block = MagicMock()  # Mock out .handle_new_block
    #     bm.build_task_list()
    #
    #     # Mock Envelope.from_bytes to return a mock envelope of our choosing
    #     mock_env = MagicMock()
    #     mock_block_notif = MagicMock(spec=NewBlockNotification)
    #     fake_hash = 'DEADBEEF' * 8
    #     mock_env.message = mock_block_notif
    #     mock_env.message_hash = fake_hash
    #
    #     with mock.patch.object(Envelope, 'from_bytes', return_value=mock_env):
    #         # It doesnt actually matter what we pass in to bm.handle_sub_msg, since we've fixed Envelope.from_bytes
    #         # to return mock_env
    #         bm.handle_sub_msg([b'filter doesnt matter', b'envelope binary also doesnt matter'])
    #
    #     # Now, actually assert handle_new_block was called with mock_env as an arg
    #     bm.handle_new_block.assert_called_with(mock_env)

if __name__ == '__main__':
    unittest.main()
