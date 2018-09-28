from cilantro.logger.base import get_logger
from cilantro.constants.testnet import TESTNET_DELEGATES
from cilantro.nodes.delegate.block_manager import BlockManager, IPC_PORT
from cilantro.utils import int_to_bytes

from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.block_data.block_metadata import NewBlockNotification

_log = get_logger("TestBlockManager")

TEST_IP = '127.0.0.1'
TEST_SK = TESTNET_DELEGATES[0]['sk']

class TestBlockManager(TestCase):

    # TODO we can probly DRY all this patching/setup code in a setup method or something
    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.SubBlockBuilder", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.asyncio", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.BlockManager.run", autospec=True)
    def test_build_task_list_creates_ipc_router(self, mock_run_method, mock_bm_asyncio, mock_sbb, mock_manager, mock_worker_asyncio):
        bm = BlockManager(ip=TEST_IP, signing_key=TEST_SK)

        # Attach a mock SockManager so create_socket calls return mock objects. Whenever a method is called on a mock
        # object, a new mock object is automatically returned
        mock_manager = MagicMock()
        bm.manager = mock_manager

        # Mock manager.create_socket(...) to return a predictable list of mock objects that we can further assert on.
        # Relies on the sockets being created in EXACTLY the same order they are specified here in 'side_effect=[...]'
        mock_tcp_router = MagicMock()
        mock_ipc_router = MagicMock()
        mock_pub = MagicMock()
        mock_sub = MagicMock()
        mock_manager.create_socket = MagicMock(side_effect=[mock_tcp_router, mock_ipc_router, mock_pub, mock_sub])

        mock_router_handler_task = MagicMock()
        mock_tcp_router.add_handler = MagicMock(return_value=mock_router_handler_task)
        mock_ipc_router.add_handler = MagicMock(return_value=mock_router_handler_task)
        mock_pub.add_handler = MagicMock(return_value=mock_router_handler_task)
        mock_sub.add_handler = MagicMock(return_value=mock_router_handler_task)

        # Since we mocked out the .run method, we must invoke build_task_list manually
        bm.build_task_list()

        # Assert 'bind' was called on ipc_router with the expected args
        self.assertEqual(bm.ipc_router, mock_ipc_router)
        self.assertEqual(bm.router, mock_tcp_router)
        mock_ipc_router.bind.assert_called_with(port=IPC_PORT, protocol='ipc', ip=bm.ipc_ip)
        mock_ipc_router.add_handler.assert_called()
        self.assertTrue(mock_router_handler_task in bm.tasks)

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.SubBlockBuilder", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.asyncio", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.BlockManager.run", autospec=True)
    def test_handle_ipc_msg(self, mock_run_method, mock_bm_asyncio, mock_sbb, mock_manager, mock_worker_asyncio):
        bm = BlockManager(ip=TEST_IP, signing_key=TEST_SK)
        bm.manager = MagicMock()
        bm.ipc_router = MagicMock()

        bm.start_sbb_procs()

        frames = [b'', b'', b'this should be a real message binary']

        # bm.handle_ipc_msg(frames)

        # TODO assert handle_ipc_msg does what expected

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.SubBlockBuilder", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.asyncio", autospec=True)
    @mock.patch("cilantro.nodes.delegate.block_manager.BlockManager.run", autospec=True)
    def test_sub_msg_with_new_block_notification_calls_handle_new_block(self, mock_run_method, mock_bm_asyncio,
                                                                        mock_sbb, mock_manager, mock_worker_asyncio):
        """
        Tests handle_sub_msg correctly calls handle_new_block when a NewBlockNotification is received
        """
        bm = BlockManager(ip=TEST_IP, signing_key=TEST_SK)
        bm.manager = MagicMock()
        bm.handle_new_block = MagicMock()  # Mock out .handle_new_block
        bm.build_task_list()

        # Mock Envelope.from_bytes to return a mock envelope of our choosing
        mock_env = MagicMock()
        mock_block_notif = MagicMock(spec=NewBlockNotification)
        fake_hash = 'DEADBEEF' * 8
        mock_env.message = mock_block_notif
        mock_env.message_hash = fake_hash

        with mock.patch.object(Envelope, 'from_bytes', return_value=mock_env):
            # It doesnt actually matter what we pass in to bm.handle_sub_msg, since we've fixed Envelope.from_bytes
            # to return mock_env
            bm.handle_sub_msg([b'filter doesnt matter', b'envelope binary also doesnt matter'])

        # Now, actually assert handle_new_block was called with mock_env as an arg
        bm.handle_new_block.assert_called_with(mock_env)






if __name__ == "__main__":
    import unittest
    unittest.main()
