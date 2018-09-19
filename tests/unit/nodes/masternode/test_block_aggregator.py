from cilantro.logger.base import get_logger
from cilantro.constants.testnet import TESTNET_MASTERNODES
from cilantro.nodes.masternode.block_aggregator import BlockAggregator
from cilantro.storage.db import VKBook

import unittest
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock
from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER, MASTER_MASTER_FILTER
from cilantro.constants.ports import MN_SUB_BLOCK_PORT, INTER_MASTER_PORT
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.full_block_hash import FullBlockHash
from cilantro.messages.consensus.merkle_signature import build_test_merkle_sig
from cilantro.constants.delegate import NODES_REQUIRED_CONSENSUS
from cilantro.utils.hasher import Hasher

TEST_IP = '127.0.0.1'
TEST_SK = TESTNET_MASTERNODES[0]['sk']
TEST_VK = TESTNET_MASTERNODES[0]['vk']
INPUT_PUSH = b'1111111111111111111111111111111111111111111111111111111111111111'
INPUT_PUSH_1 = b'2222222222222222222222222222222222222222222222222222222222222222'
RESULT_HASH = b'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'
RESULT_HASH_1 = b'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
RAWTXS = [
    b'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    b'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
    b'CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
    b'DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD',
    b'EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE'
]
MERKLE_LEAVES = [
    Hasher.hash(tx) for tx in RAWTXS
]

class TestBlockAggregator(TestCase):

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_build_task_list_connect_and_bind(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        mock_manager = MagicMock()
        ba.manager = mock_manager

        mock_pub, mock_sub = MagicMock(), MagicMock()
        mock_manager.create_socket = MagicMock(side_effect=[mock_sub, mock_pub])

        mock_sub_handler_task = MagicMock()
        mock_sub.add_handler = MagicMock(return_value=mock_sub_handler_task)

        ba.build_task_list()

        self.assertEqual(ba.sub, mock_sub)
        self.assertEqual(ba.pub, mock_pub)
        mock_sub.add_handler.assert_called()
        self.assertTrue(mock_sub_handler_task in ba.tasks)

        self.assertEqual(mock_sub.connect.call_count,
            len([vk for vk in VKBook.get_masternodes() if TEST_VK != vk]) + \
                len([vk for vk in VKBook.get_delegates() if TEST_VK != vk]))

        mock_pub.bind.assert_called_with(ip=TEST_IP, port=INTER_MASTER_PORT)

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_handle_recv_sub_block_contender(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.recv_sub_block_contender = MagicMock()
        ba.build_task_list()

        mock_env = MagicMock()
        mock_env.message = MagicMock(spec=SubBlockContender)

        with mock.patch.object(Envelope, 'from_bytes', return_value=mock_env):
            ba.handle_sub_msg([b'filter doesnt matter', b'envelope binary also doesnt matter'])

        ba.recv_sub_block_contender.assert_called_with(mock_env.message)

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_handle_recv_result_hash(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.recv_result_hash = MagicMock()
        ba.build_task_list()

        mock_env = MagicMock()
        mock_env.message = MagicMock(spec=FullBlockHash)

        with mock.patch.object(Envelope, 'from_bytes', return_value=mock_env):
            ba.handle_sub_msg([b'filter doesnt matter', b'envelope binary also doesnt matter'])

        ba.recv_result_hash.assert_called_with(mock_env.message)

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_recv_sub_block_contender(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()

        signature = build_test_merkle_sig()
        sbc = SubBlockContender.create(RESULT_HASH, INPUT_PUSH, MERKLE_LEAVES, signature, RAWTXS)

        ba.recv_sub_block_contender(sbc)

        self.assertEqual(ba.contenders[RESULT_HASH]['sbc']._data.inputHash, INPUT_PUSH)

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_recv_sub_block_contender_fail(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()

        signature = build_test_merkle_sig()
        sbc = SubBlockContender.create(RESULT_HASH, INPUT_PUSH, MERKLE_LEAVES, signature, RAWTXS)

        sbc._data.resultHash = b'A' * 63

        with self.assertRaises(AssertionError):
            ba.recv_sub_block_contender(sbc)

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_combine_result_hash(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()
        ba.pub = MagicMock()
        ba.pub.send_msg = MagicMock()

        for i in range(NODES_REQUIRED_CONSENSUS):
            signature = build_test_merkle_sig()
            sbc = SubBlockContender.create(RESULT_HASH, INPUT_PUSH, MERKLE_LEAVES, signature, RAWTXS)
            ba.recv_sub_block_contender(sbc)

        fbh = FullBlockHash.create(RESULT_HASH)
        ba.pub.send_msg.assert_called_with(msg=fbh._data.fullBlockHash, header=MASTER_MASTER_FILTER.encode())

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_combine_result_hash_transactions_missing(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()

        for i in range(NODES_REQUIRED_CONSENSUS):
            signature = build_test_merkle_sig()
            sbc = SubBlockContender.create(RESULT_HASH, INPUT_PUSH, MERKLE_LEAVES, signature, RAWTXS[:3])
            ba.recv_sub_block_contender(sbc)

        self.assertEqual(len(ba.contenders[RESULT_HASH]['signatures_received']), NODES_REQUIRED_CONSENSUS)
        self.assertEqual(len(ba.contenders[RESULT_HASH]['merkle_hashes_received']), 3)

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.SUBBLOCKS_REQUIRED", 2)
    def test_recv_result_hash_multiple_subblocks(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)
        ba.manager = MagicMock()
        ba.build_task_list()

        # Sub block 0
        for i in range(NODES_REQUIRED_CONSENSUS):
            signature = build_test_merkle_sig()
            sbc = SubBlockContender.create(RESULT_HASH, INPUT_PUSH, MERKLE_LEAVES, signature, RAWTXS)
            ba.recv_sub_block_contender(sbc)

        # Sub block 1
        for i in range(NODES_REQUIRED_CONSENSUS):
            signature = build_test_merkle_sig()
            sbc = SubBlockContender.create(RESULT_HASH_1, INPUT_PUSH_1, MERKLE_LEAVES, signature, RAWTXS)
            ba.recv_sub_block_contender(sbc)

        fbh = FullBlockHash.create(b''.join(sorted(ba.contenders.keys())))
        self.assertEqual(ba.full_block_hashes.get(fbh._data.fullBlockHash), 1)

if __name__ == '__main__':
    unittest.main()
