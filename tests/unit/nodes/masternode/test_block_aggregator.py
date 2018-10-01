from cilantro.logger.base import get_logger
from cilantro.nodes.masternode.block_aggregator import BlockAggregator
from cilantro.storage.db import VKBook
from cilantro.storage.db import reset_db

from cilantro.constants.system_config import DELEGATE_MAJORITY

import unittest
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock

from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER, MASTER_MASTER_FILTER, DEFAULT_FILTER
from cilantro.constants.ports import MASTER_ROUTER_PORT, MASTER_PUB_PORT, DELEGATE_PUB_PORT, DELEGATE_ROUTER_PORT

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.transaction.contract import ContractTransactionBuilder
from cilantro.messages.transaction.data import TransactionData

from cilantro.messages.block_data.block_data import *
from cilantro.messages.block_data.state_update import *
from cilantro.messages.block_data.block_metadata import *

from cilantro.utils.hasher import Hasher
from cilantro.protocol.structures.merkle_tree import MerkleTree
from cilantro.protocol import wallet

TEST_IP = '127.0.0.1'
TEST_SK = TESTNET_MASTERNODES[0]['sk']
TEST_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_DELEGATES[0]['vk']
INPUT_HASH = '1111111111111111111111111111111111111111111111111111111111111111'
INPUT_HASH_1 = '2222222222222222222222222222222222222222222222222222222222222222'
RAWTXS = [
    b'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    b'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
    b'CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
    b'DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD',
    b'EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE'
]
RAWTXS_1 = [
    b'1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    b'2BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
    b'3CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
    b'4DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD',
    b'5EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE'
]
TXS = [TransactionData.create(
    contract_tx=ContractTransactionBuilder.create_contract_tx(sender_sk=TEST_SK, code_str=raw_tx.decode()),
    status='SUCCESS', state='blah'
    ) for raw_tx in RAWTXS]
TXS_1 = [TransactionData.create(
    contract_tx=ContractTransactionBuilder.create_contract_tx(sender_sk=TEST_SK, code_str=raw_tx.decode()),
    status='SUCCESS', state='blah'
    ) for raw_tx in RAWTXS_1]
MERKLE_LEAVES = [Hasher.hash(tx) for tx in TXS]
MERKLE_LEAVES_1 = [Hasher.hash(tx) for tx in TXS_1]

RESULT_HASH = MerkleTree.from_hex_leaves(MERKLE_LEAVES).root_as_hex
RESULT_HASH_1 = MerkleTree.from_hex_leaves(MERKLE_LEAVES_1).root_as_hex

log = get_logger('BlockAggregator')


class TestBlockAggregator(TestCase):

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_build_task_list_connect_and_bind(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        mock_manager = MagicMock()
        ba.manager = mock_manager

        mock_pub, mock_sub, mock_router = MagicMock(), MagicMock(), MagicMock()
        mock_manager.create_socket = MagicMock(side_effect=[mock_sub, mock_pub, mock_router])

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

        mock_pub.bind.assert_called_with(ip=TEST_IP, port=MASTER_PUB_PORT)

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_handle_sub_msg_with_sub_block_contender(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):
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
    def test_handle_sub_msg_with_new_block_notif(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.recv_new_block_notif = MagicMock()
        ba.build_task_list()

        mock_env = MagicMock()
        mock_env.message = MagicMock(spec=NewBlockNotification)

        with mock.patch.object(Envelope, 'from_bytes', return_value=mock_env):
            ba.handle_sub_msg([b'filter doesnt matter', b'envelope binary also doesnt matter'])

        ba.recv_new_block_notif.assert_called_with(mock_env.message)

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_recv_sub_block_contender(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()

        signature = build_test_merkle_sig(msg=RESULT_HASH.encode(),sk=DEL_SK, vk=DEL_VK)
        sbc = SubBlockContender.create(RESULT_HASH, INPUT_HASH, MERKLE_LEAVES, signature, TXS, 0)

        ba.recv_sub_block_contender(sbc)
        self.assertTrue(sbc._data.signature in ba.result_hashes[RESULT_HASH]['signatures'])

    @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
    @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
    def test_combine_result_hash_transactions_missing(self, mock_run_method, mock_bm_asyncio, mock_worker_asyncio):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()

        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=RESULT_HASH.encode(),sk=DEL_SK, vk=DEL_VK)
            sbc = SubBlockContender.create(RESULT_HASH, INPUT_HASH, MERKLE_LEAVES, signature, TXS, 0)
            ba.recv_sub_block_contender(sbc)

        self.assertEqual(len(ba.result_hashes[RESULT_HASH]['signatures']), DELEGATE_MAJORITY)
        self.assertEqual(len(ba.contenders[INPUT_HASH]['transactions']), 5)
        self.assertEqual(len(ba.full_block_hashes), 0)


# TODO fix these tests?
# class TestBlockAggregatorStorage(TestCase):
#
#     def setUp(self):
#         reset_db()
#
#     @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
#     @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
#     @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
#     @mock.patch("cilantro.constants.system_config.NUM_SUB_BLOCKS", 1)
#     @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SUB_BLOCKS", 1)
#     def test_combine_result_hash(self, *args):
#         ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)
#
#         ba.manager = MagicMock()
#         ba.build_task_list()
#         ba.pub = MagicMock()
#         old_b_hash = ba.curr_block_hash
#
#         for i in range(DELEGATE_MAJORITY):
#             signature = build_test_merkle_sig(msg=RESULT_HASH.encode(),sk=DEL_SK, vk=DEL_VK)
#             sbc = SubBlockContender.create(RESULT_HASH, INPUT_HASH, MERKLE_LEAVES, signature, TXS, 0)
#             ba.recv_sub_block_contender(sbc)
#
#         tree = MerkleTree.from_hex_leaves(MERKLE_LEAVES)
#         signature = MerkleSignature.create(sig_hex=wallet.sign(TEST_SK, ba.curr_block_hash.encode()), timestamp=str(time.time()), sender=ba.verifying_key)
#         new_block_notif = NewBlockNotification.create(
#             block_hash=ba.curr_block_hash,
#             merkle_roots=sorted(ba.contenders.keys()),
#             prev_block_hash=old_b_hash,
#             masternode_signature=signature
#         )
#         ba.pub.send_msg.assert_called_with(msg=new_block_notif, header=DEFAULT_FILTER.encode())
#
#     @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
#     @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
#     @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
#     def test_recv_ignore_extra_sub_block_contenders(self, *args):
#
#         ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)
#         ba.manager = MagicMock()
#         ba.build_task_list()
#         bh = ba.curr_block_hash
#         for i in range(DELEGATE_MAJORITY + 5):
#             signature = build_test_merkle_sig(msg=RESULT_HASH.encode(),sk=DEL_SK, vk=DEL_VK)
#             sbc = SubBlockContender.create(RESULT_HASH, INPUT_HASH, MERKLE_LEAVES, signature, TXS, 0)
#             ba.recv_sub_block_contender(sbc)
#
#         tree = MerkleTree.from_hex_leaves(MERKLE_LEAVES)
#         signature = MerkleSignature.create(sig_hex=wallet.sign(TEST_SK, tree.root), timestamp=str(time.time()), sender=ba.verifying_key)
#         new_block_notif = NewBlockNotification.create(
#             block_hash=ba.curr_block_hash,
#             merkle_roots=sorted(ba.contenders.keys()),
#             prev_block_hash=bh,
#             masternode_signature=signature
#         )
#         ba.pub.send_msg.assert_called_with(msg=new_block_notif, header=DEFAULT_FILTER.encode())
#
#     @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
#     @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
#     @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
#     @mock.patch("cilantro.constants.system_config.NUM_SUB_BLOCKS", 2)
#     @mock.patch("cilantro.nodes.masternode.block_aggregator.MASTERNODE_MAJORITY", 3)
#     @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SUB_BLOCKS", 2)
#     def test_recv_result_hash_multiple_subblocks_consensus(self, *args):
#
#         ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)
#         ba.manager = MagicMock()
#         ba.build_task_list()
#         bh = ba.curr_block_hash
#
#         # Sub block 0
#         for i in range(DELEGATE_MAJORITY):
#             signature = build_test_merkle_sig(msg=RESULT_HASH.encode(),sk=DEL_SK, vk=DEL_VK)
#             sbc = SubBlockContender.create(RESULT_HASH, INPUT_HASH, MERKLE_LEAVES, signature, TXS, 0)
#             ba.recv_sub_block_contender(sbc)
#
#         # Sub block 1
#         for i in range(DELEGATE_MAJORITY):
#             signature = build_test_merkle_sig(msg=RESULT_HASH_1.encode(),sk=DEL_SK, vk=DEL_VK)
#             sbc = SubBlockContender.create(RESULT_HASH_1, INPUT_HASH_1, MERKLE_LEAVES_1, signature, TXS_1, 1)
#             ba.recv_sub_block_contender(sbc)
#
#         self.assertEqual(ba.total_valid_sub_blocks, 2)
#
#         tree = MerkleTree.from_hex_leaves(MERKLE_LEAVES+MERKLE_LEAVES_1)
#         signature = MerkleSignature.create(sig_hex=wallet.sign(TEST_SK, tree.root), timestamp=str(time.time()), sender=ba.verifying_key)
#         new_block_notif = NewBlockNotification.create(
#             block_hash=ba.curr_block_hash,
#             merkle_roots=sorted(ba.contenders.keys()),
#             prev_block_hash=bh,
#             masternode_signature=signature
#         )
#         for i in range(3):
#             ba.recv_new_block_notif(new_block_notif)
#
#         self.assertEqual(ba.full_block_hashes[ba.curr_block_hash]['consensus_count'], 3)
#         self.assertEqual(ba.full_block_hashes[ba.curr_block_hash]['full_block_metadata'], new_block_notif)
#         self.assertEqual(ba.total_valid_sub_blocks, 0)
#
#     @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
#     @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
#     @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
#     @mock.patch("cilantro.constants.system_config.NUM_SUB_BLOCKS", 2)
#     @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SUB_BLOCKS", 2)
#     def test_recv_result_hash_multiple_subblocks(self, *args):
#
#         ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)
#         ba.manager = MagicMock()
#         ba.build_task_list()
#         bh = ba.curr_block_hash
#
#         # Sub block 0
#         for i in range(DELEGATE_MAJORITY):
#             signature = build_test_merkle_sig(msg=RESULT_HASH.encode(),sk=DEL_SK, vk=DEL_VK)
#             sbc = SubBlockContender.create(RESULT_HASH, INPUT_HASH, MERKLE_LEAVES, signature, TXS, 0)
#             ba.recv_sub_block_contender(sbc)
#
#         # Sub block 1
#         for i in range(DELEGATE_MAJORITY):
#             signature = build_test_merkle_sig(msg=RESULT_HASH_1.encode(),sk=DEL_SK, vk=DEL_VK)
#             sbc = SubBlockContender.create(RESULT_HASH_1, INPUT_HASH_1, MERKLE_LEAVES_1, signature, TXS_1, 1)
#             ba.recv_sub_block_contender(sbc)
#
#         # sub_block_hashes = sorted(ba.contenders.keys(), key=lambda input_hash: ba.contenders[input_hash]['sb_index'])
#         # block_hash = Hasher.hash_iterable([*sub_block_hashes, bh])
#         # self.assertEqual(ba.full_block_hashes[block_hash]['full_block_metadata'].merkle_roots, sub_block_hashes)
#         self.assertEqual(ba.total_valid_sub_blocks, 2)


if __name__ == '__main__':
    unittest.main()
