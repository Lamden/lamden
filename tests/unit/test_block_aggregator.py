from deprecated.test import set_testnet_config
set_testnet_config('vk_dump.json')
from cilantro_ee.constants.testnet import set_testnet_nodes
set_testnet_nodes()

from cilantro_ee.nodes.masternode.block_aggregator import BlockAggregator

import unittest, asyncio
from unittest import TestCase, mock
from unittest.mock import MagicMock

from cilantro_ee.constants.ports import MN_PUB_PORT
from cilantro_ee.constants.system_config import *

from cilantro_ee.messages.envelope.envelope import Envelope
from cilantro_ee.messages.consensus.sub_block_contender import SubBlockContender
from cilantro_ee.messages.transaction.contract import ContractTransactionBuilder

from cilantro_ee.messages.block_data.block_data import *
from cilantro_ee.messages.block_data.state_update import *
from cilantro_ee.messages.block_data.block_metadata import *
from cilantro_ee.messages.consensus.merkle_signature import *

from cilantro_ee.core.containers.merkle_tree import MerkleTree
from cilantro_ee.services.storage.driver import SafeDriver
from cilantro_ee.services.storage.vkbook import PhoneBook, VKBook

# time and logger are for debugging
from cilantro_ee.core.logger.base import get_logger


class BlockAggTester:
    @staticmethod
    def test(func):
        @mock.patch("cilantro_ee.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 2)
        @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
        @mock.patch("cilantro_ee.nodes.masternode.block_contender.NUM_SB_PER_BLOCK", 2)
        # @mock.patch("cilantro_ee.core.utils.worker.asyncio")
        @mock.patch("cilantro_ee.core.utils.worker.SocketManager")
        @mock.patch("cilantro_ee.nodes.masternode.block_aggregator.BlockAggregator.run")
        def _func(*args, **kwargs):
            return func(*args, **kwargs)
        return _func


TEST_IP = '127.0.0.1'
TEST_SK = TESTNET_MASTERNODES[0]['sk']
TEST_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_DELEGATES[0]['vk']

TEST_DELEGATES = [TESTNET_DELEGATES[i]['vk'] for i in range(len(TESTNET_DELEGATES))]
TEST_MASTERS = [TESTNET_MASTERNODES[i]['vk'] for i in range(len(TESTNET_MASTERNODES))]

INPUT_HASH1 = '1' * 64
INPUT_HASH2 = '2' * 64
RAWTXS1 = [
    b'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    b'BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
    b'CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
    b'DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD',
    b'EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE'
]
RAWTXS2 = [
    b'1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    b'2BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB',
    b'3CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC',
    b'4DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD',
    b'5EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE'
]
TXS1 = [TransactionData.create(
    contract_tx=ContractTransactionBuilder.create_currency_tx(sender_sk=TEST_SK, receiver_vk=raw_tx.decode(), amount=10),
    status='SUCCESS', state='x 1') for raw_tx in RAWTXS1]
TXS2 = [TransactionData.create(
    contract_tx=ContractTransactionBuilder.create_currency_tx(sender_sk=TEST_SK, receiver_vk=raw_tx.decode(), amount=10),
    status='SUCCESS', state='x 1') for raw_tx in RAWTXS2]

TREE1 = MerkleTree.from_raw_transactions([t.serialize() for t in TXS1])
TREE2 = MerkleTree.from_raw_transactions([t.serialize() for t in TXS2])

MERKLE_LEAVES1 = TREE1.leaves
MERKLE_LEAVES2 = TREE2.leaves

RESULT_HASH1 = TREE1.root_as_hex
RESULT_HASH2 = TREE2.root_as_hex

log = get_logger('BlockAggregatorTester')


class TestBlockAggregator(TestCase):
    def setUp(self):
        SafeDriver.flush()

    @BlockAggTester.test
    def test_build_task_list_connect_and_bind(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)

        # tasks is usually self.manager.overlay_client.tasks, (which in this case is mocked out), so we must do thus:
        ba.tasks = []

        mock_manager = MagicMock()
        ba.manager = mock_manager

        mock_pub, mock_sub, mock_router, mock_ipc_router = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        mock_manager.create_socket = MagicMock(side_effect=[mock_sub, mock_pub, mock_router, mock_ipc_router])
        mock_manager.is_ready = MagicMock(return_value=True)

        mock_sub_handler_task = MagicMock()
        mock_sub.add_handler = MagicMock(return_value=mock_sub_handler_task)

        ba.build_task_list()
        ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)

        self.assertEqual(ba.sub, mock_sub)
        self.assertEqual(ba.pub, mock_pub)
        mock_sub.add_handler.assert_called()
        self.assertTrue(mock_sub_handler_task in ba.tasks)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ba._connect_and_process())
        loop.close()

        expected_num_mn_subs = len([vk for vk in PhoneBook.masternodes if TEST_VK != vk])
        expected_num_delegate_subs = len(PhoneBook.delegates)
        self.assertEqual(mock_sub.connect.call_count, expected_num_mn_subs + expected_num_delegate_subs)

        mock_pub.bind.assert_called_with(ip=TEST_IP, port=MN_PUB_PORT)

    # TODO fix this test --davis
    # @BlockAggTester.test
    # def test_store_block(self, *args):
    #     ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)
    #     ba.manager = MagicMock()
    #     ba.send_new_block_notif = MagicMock()
    #     ba.build_task_list()
    #     ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)
    #
    #     sk1, vk1 = wallet._new()
    #     sk2, vk2 = wallet._new()
    #     sk3, vk3 = wallet._new()
    #     sk4, vk4 = wallet._new()
    #
    #     sb1_txs = [TransactionDataBuilder.create_random_tx() for _ in range(8)]
    #     sb2_txs = [TransactionDataBuilder.create_random_tx() for _ in range(8)]
    #     sb1_txs_hashes = {Hasher.hash(tx): tx for tx in sb1_txs}
    #     sb2_txs_hashes = {Hasher.hash(tx): tx for tx in sb2_txs}
    #
    #     tree1 = MerkleTree.from_transactions(sb1_txs)
    #     tree2 = MerkleTree.from_transactions(sb2_txs)
    #
    #     sig1, sig2 = MerkleSignature.create_from_payload(sk1, tree1.root), MerkleSignature.create_from_payload(sk2, tree1.root)
    #     sig3, sig4 = MerkleSignature.create_from_payload(sk3, tree2.root), MerkleSignature.create_from_payload(sk4, tree2.root)
    #
    #     input_hash1 = 'AB' * 32  # Input hashes are the hashes of the transaction bags
    #     input_hash2 = 'BA' * 32
    #     result_hash1 = tree1.root_as_hex  # Result hashes are the merkle roots
    #     result_hash2 = tree2.root_as_hex
    #
    #     ba.result_hashes[result_hash1] = {'_committed_': False, '_consensus_reached_': True,
    #                                       '_transactions_': sb1_txs_hashes,
    #                                       '_valid_signatures_': {sig1.signature: sig1, sig2.signature: sig2},
    #                                       '_input_hash_': input_hash1, '_merkle_leaves_': tree1.leaves_as_hex,
    #                                       '_sb_index_': 0, '_lastest_valid_': time.time()}
    #     ba.result_hashes[result_hash2] = {'_committed_': False, '_consensus_reached_': True,
    #                                       '_transactions_': sb2_txs_hashes,
    #                                       '_valid_signatures_': {sig3.signature: sig3, sig4.signature: sig4},
    #                                       '_input_hash_': input_hash2, '_merkle_leaves_': tree2.leaves_as_hex,
    #                                       '_sb_index_': 1, '_lastest_valid_': time.time()}
    #
    #     ba.store_full_block()
    #
    #     block_data = ba.send_new_block_notif.call_args[0][0]
    #     block_data = ba.send_new_block_notif.call_args[0][0]
    #
    #     self.assertEqual(block_data.sub_blocks[0].input_hash, input_hash1)
    #     self.assertEqual(block_data.sub_blocks[1].input_hash, input_hash2)
    #     self.assertEqual(block_data.sub_blocks[0].merkle_root, result_hash1)
    #     self.assertEqual(block_data.sub_blocks[1].merkle_root, result_hash2)
    #     self.assertEqual(block_data.sub_blocks[0].transactions, sb1_txs)
    #     self.assertEqual(block_data.sub_blocks[1].transactions, sb2_txs)
    #     self.assertEqual(block_data.sub_blocks[0].signatures, [sig1, sig2])
    #     self.assertEqual(block_data.sub_blocks[1].signatures, [sig3, sig4])

    @BlockAggTester.test
    def test_handle_sub_msg_with_sub_block_contender(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)

        ba.manager = MagicMock()
        ba.recv_sub_block_contender = MagicMock()
        ba.build_task_list()
        ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)

        mock_env = MagicMock()
        mock_env.message = MagicMock(spec=SubBlockContender)

        with mock.patch.object(Envelope, 'from_bytes', return_value=mock_env):
            ba.handle_sub_msg([b'filter doesnt matter', b'envelope binary also doesnt matter'])

        ba.recv_sub_block_contender.assert_called()

    @BlockAggTester.test
    def test_handle_sub_msg_with_new_block_notif(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)

        ba.manager = MagicMock()
        ba.recv_new_block_notif = MagicMock()
        ba.build_task_list()
    
        ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)

        mock_env = MagicMock()
        mock_env.message = MagicMock(spec=NewBlockNotification)

        with mock.patch.object(Envelope, 'from_bytes', return_value=mock_env):
            ba.handle_sub_msg([b'filter doesnt matter', b'envelope binary also doesnt matter'])

        ba.recv_new_block_notif.assert_called()

    @BlockAggTester.test
    def test_recv_sub_block_contender(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)

        ba.manager = MagicMock()
        ba.build_task_list()
        ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)

        signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=DEL_SK, vk=DEL_VK)

        PhoneBook = VKBook(delegates=[DEL_VK, TESTNET_DELEGATES[1]['vk']], masternodes=[TESTNET_MASTERNODES[0]])

        sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0, GENESIS_BLOCK_HASH)

        ba.recv_sub_block_contender(DEL_VK, sbc)
        self.assertTrue(sbc in ba.curr_block.sb_groups[0].rh[RESULT_HASH1])


    @BlockAggTester.test
    def test_recv_empty_sub_block_contender(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)

        ba.manager = MagicMock()
        ba.build_task_list()
        ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)

        signature = build_test_merkle_sig(msg=bytes.fromhex(INPUT_HASH1), sk=DEL_SK, vk=DEL_VK)

        PhoneBook = VKBook(delegates=[DEL_VK, TESTNET_DELEGATES[1]['vk']], masternodes=[TESTNET_MASTERNODES[0]])

        sbc = SubBlockContender.create_empty_sublock(INPUT_HASH1, sub_block_index=0, signature=signature,
                                                     prev_block_hash=GENESIS_BLOCK_HASH)

    @BlockAggTester.test
    @mock.patch("cilantro_ee.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.nodes.masternode.block_contender.NUM_SB_PER_BLOCK", 1)
    def test_combine_result_hash_with_one_sb(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)

        ba.manager = MagicMock()
        ba.send_new_block_notif = MagicMock()
        ba.build_task_list()
        ba.pub = MagicMock()
        old_b_hash = ba.curr_block_hash
        ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)

        PhoneBook = VKBook(delegates=TEST_DELEGATES, masternodes=TEST_MASTERS)

        # Sub block 0
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0, GENESIS_BLOCK_HASH)
            ba.recv_sub_block_contender(TESTNET_DELEGATES[i]['vk'], sbc)

        block_data = ba.send_new_block_notif.call_args[0][0]
        self.assertEqual(block_data.prev_block_hash, old_b_hash)
        self.assertEqual(block_data.merkle_roots, [RESULT_HASH1])
        self.assertEqual(block_data.transactions, TXS1)

    @BlockAggTester.test
    def test_combine_result_hash_with_multiple_sb(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)

        ba.manager = MagicMock()
        ba.build_task_list()
        ba.send_new_block_notif = MagicMock()
        old_b_hash = ba.curr_block_hash

        PhoneBook = VKBook(delegates=TEST_DELEGATES, masternodes=TEST_MASTERS)

        # Sub block 0
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0, GENESIS_BLOCK_HASH)
            ba.recv_sub_block_contender(TESTNET_DELEGATES[i]['vk'], sbc)

        # Sub block 1
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH2), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH2, INPUT_HASH2, MERKLE_LEAVES2, signature, TXS2, 1, GENESIS_BLOCK_HASH)
            ba.recv_sub_block_contender(TESTNET_DELEGATES[i]['vk'], sbc)

        block_data = ba.send_new_block_notif.call_args[0][0]
        self.assertEqual(block_data.prev_block_hash, old_b_hash)
        self.assertEqual(block_data.merkle_roots, [RESULT_HASH1, RESULT_HASH2])
        self.assertEqual(block_data.transactions, TXS1 + TXS2)

    @BlockAggTester.test
    def test_combine_result_hash_with_multiple_sb_with_extras(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)

        ba.manager = MagicMock()
        ba.send_new_block_notif = MagicMock()
        ba.build_task_list()
        ba.pub = MagicMock()
        old_b_hash = ba.curr_block_hash
        ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)

        PhoneBook = VKBook(delegates=TEST_DELEGATES, masternodes=TEST_MASTERS)
        num_delegates = len(TEST_DELEGATES)

        # Sub block 0
        for i in range(num_delegates):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0, GENESIS_BLOCK_HASH)
            ba.recv_sub_block_contender(TESTNET_DELEGATES[i]['vk'], sbc)

        # Sub block 1
        for i in range(num_delegates):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH2), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH2, INPUT_HASH2, MERKLE_LEAVES2, signature, TXS2, 1, GENESIS_BLOCK_HASH)
            ba.recv_sub_block_contender(TESTNET_DELEGATES[i]['vk'], sbc)

        block_data = ba.send_new_block_notif.call_args[0][0]
        self.assertEqual(block_data.prev_block_hash, old_b_hash)
        self.assertEqual(block_data.merkle_roots, [RESULT_HASH1, RESULT_HASH2])
        self.assertEqual(block_data.transactions, TXS1 + TXS2)

    @BlockAggTester.test
    @mock.patch("cilantro_ee.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.nodes.masternode.block_contender.NUM_SB_PER_BLOCK", 1)
    def test_recv_ignore_extra_sub_block_contenders(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)
        ba.manager = MagicMock()
        ba.build_task_list()
        ba.send_new_block_notif = MagicMock()
        ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)
        old_b_hash = ba.curr_block_hash

        for i in range(DELEGATE_MAJORITY + 5):
            vk = TESTNET_DELEGATES[i%len(TESTNET_DELEGATES)]['vk']
            sk = TESTNET_DELEGATES[i%len(TESTNET_DELEGATES)]['sk']
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=sk, vk=vk)
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0, GENESIS_BLOCK_HASH)
            ba.recv_sub_block_contender(vk, sbc)

        block_data = ba.send_new_block_notif.call_args[0][0]
        self.assertEqual(block_data.prev_block_hash, old_b_hash)
        self.assertEqual(block_data.merkle_roots, [RESULT_HASH1])
        self.assertEqual(block_data.transactions, TXS1)

    # TODO fix this test once we care about getting consensus on _new block notifications --davis
    # @BlockAggTester.test
    # @mock.patch("cilantro_ee.nodes.masternode.block_aggregator.MASTERNODE_MAJORITY", 2)
    # @mock.patch("cilantro_ee.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 2)
    # @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
    # def test_recv_result_hash_multiple_subblocks_consensus(self, *args):
    #
    #     ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)
    #     ba.manager = MagicMock()
    #     ba.build_task_list()
    #     ba.is_catching_up = False
    #     ba.pub = MagicMock()
    #     bh = ba.curr_block_hash
    #
    #     # Sub block 0
    #     for i in range(DELEGATE_MAJORITY):
    #         signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
    #         sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0, GENESIS_BLOCK_HASH)
    #         ba.recv_sub_block_contender(sbc)
    #
    #     # Sub block 1
    #     for i in range(DELEGATE_MAJORITY):
    #         signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH2), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
    #         sbc = SubBlockContender.create(RESULT_HASH2, INPUT_HASH2, MERKLE_LEAVES2, signature, TXS2, 1, GENESIS_BLOCK_HASH)
    #         ba.recv_sub_block_contender(sbc)
    #
    #     self.assertEqual(len(ba.full_blocks), 1)
    #     block_data = ba.send_new_block_notif.call_args[0][0]
    #     nbn = NewBlockNotification.create_from_block_data(block_data)
    #
    #     mn1_vk = 'ABCD' * 16
    #     mn2_vk = 'DCBA' * 16
    #     ba.recv_new_block_notif(mn1_vk)
    #     ba.recv_new_block_notif(mn2_vk)
    #
    #     self.assertEqual(len(ba.full_blocks[ba.curr_block_hash]['_senders_']), 3)
    #     self.assertEqual(block_data.prev_block_hash, bh)
    #     self.assertEqual(block_data.merkle_roots, [RESULT_HASH1, RESULT_HASH2])
    #     self.assertEqual(block_data.transactions, TXS1 + TXS2)

    @BlockAggTester.test
    @mock.patch("cilantro_ee.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro_ee.nodes.masternode.block_contender.NUM_SB_PER_BLOCK", 1)
    def test_combine_result_hash_transactions_missing(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK, ipc_ip="test_mn-ipc-sock", ipc_port=6967)

        ba.manager = MagicMock()
        ba.build_task_list()
        ba.send_new_block_notif = MagicMock()
        ba.catchup_manager.is_catchup_done = MagicMock(return_value=True)

        PhoneBook = VKBook(delegates=TEST_DELEGATES, masternodes=TEST_MASTERS)

        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1[:3], 0, GENESIS_BLOCK_HASH)
            ba.recv_sub_block_contender(TESTNET_DELEGATES[i]['vk'], sbc)

        self.assertFalse(ba.curr_block.is_consensus_reached())

        # self.assertEqual(len(ba.result_hashes[RESULT_HASH1]['_valid_signatures_']), DELEGATE_MAJORITY)
        # self.assertEqual(len(ba.result_hashes[RESULT_HASH1]['_transactions_']), 3)
        # self.assertEqual(len(ba.full_blocks), 0)


if __name__ == '__main__':
    unittest.main()
