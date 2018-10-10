from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-4.json')

from cilantro.logger.base import get_logger
from cilantro.nodes.masternode.block_aggregator import BlockAggregator
from cilantro.storage.db import VKBook
from cilantro.storage.db import reset_db

import unittest
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock

from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER, MASTER_MASTER_FILTER, DEFAULT_FILTER
from cilantro.constants.ports import MASTER_ROUTER_PORT, MASTER_PUB_PORT, DELEGATE_PUB_PORT, DELEGATE_ROUTER_PORT
from cilantro.constants.system_config import *

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
from cilantro.storage.sqldb import SQLDB


class BlockAggTester:
    @staticmethod
    def test(func):
        @mock.patch("cilantro.protocol.multiprocessing.worker.asyncio", autospec=True)
        @mock.patch("cilantro.protocol.multiprocessing.worker.SocketManager", autospec=True)
        @mock.patch("cilantro.nodes.masternode.block_aggregator.BlockAggregator.run", autospec=True)
        def _func(*args, **kwargs):
            return func(*args, **kwargs)
        return _func


TEST_IP = '127.0.0.1'
TEST_SK = TESTNET_MASTERNODES[0]['sk']
TEST_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_DELEGATES[0]['vk']
INPUT_HASH1 = '1111111111111111111111111111111111111111111111111111111111111111'
INPUT_HASH2 = '2222222222222222222222222222222222222222222222222222222222222222'
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
    contract_tx=ContractTransactionBuilder.create_contract_tx(sender_sk=TEST_SK, code_str=raw_tx.decode()),
    status='SUCCESS', state='blah'
    ) for raw_tx in RAWTXS1]
TXS2 = [TransactionData.create(
    contract_tx=ContractTransactionBuilder.create_contract_tx(sender_sk=TEST_SK, code_str=raw_tx.decode()),
    status='SUCCESS', state='blah'
    ) for raw_tx in RAWTXS2]

TREE1 = MerkleTree.from_raw_transactions([t.serialize() for t in TXS1])
TREE2 = MerkleTree.from_raw_transactions([t.serialize() for t in TXS2])

MERKLE_LEAVES1 = TREE1.leaves
MERKLE_LEAVES2 = TREE2.leaves

RESULT_HASH1 = TREE1.root_as_hex
RESULT_HASH2 = TREE2.root_as_hex

log = get_logger('BlockAggregator')


class TestBlockAggregator(TestCase):

    @BlockAggTester.test
    def test_build_task_list_connect_and_bind(self, *args):
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

    @BlockAggTester.test
    def test_handle_sub_msg_with_sub_block_contender(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.recv_sub_block_contender = MagicMock()
        ba.build_task_list()

        mock_env = MagicMock()
        mock_env.message = MagicMock(spec=SubBlockContender)

        with mock.patch.object(Envelope, 'from_bytes', return_value=mock_env):
            ba.handle_sub_msg([b'filter doesnt matter', b'envelope binary also doesnt matter'])

        ba.recv_sub_block_contender.assert_called_with(mock_env.message)

    @BlockAggTester.test
    def test_handle_sub_msg_with_new_block_notif(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.recv_new_block_notif = MagicMock()
        ba.build_task_list()

        mock_env = MagicMock()
        mock_env.message = MagicMock(spec=NewBlockNotification)

        with mock.patch.object(Envelope, 'from_bytes', return_value=mock_env):
            ba.handle_sub_msg([b'filter doesnt matter', b'envelope binary also doesnt matter'])

        ba.recv_new_block_notif.assert_called_with(mock_env.message)

    @BlockAggTester.test
    def test_recv_sub_block_contender(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()

        signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=DEL_SK, vk=DEL_VK)
        sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0)

        ba.recv_sub_block_contender(sbc)
        self.assertTrue(sbc.signature.signature in ba.result_hashes[RESULT_HASH1]['_valid_signatures_'])


class TestBlockAggregatorStorage(TestCase):

    def setUp(self):
        reset_db()
        SQLDB.force_start()

    @BlockAggTester.test
    @mock.patch("cilantro.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
    def test_combine_result_hash_with_one_sb(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()
        ba.pub = MagicMock()
        old_b_hash = ba.curr_block_hash

        # Sub block 0
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0)
            ba.recv_sub_block_contender(sbc)

        signature = MerkleSignature.create(sig_hex=wallet.sign(TEST_SK, ba.curr_block_hash.encode()), timestamp=str(time.time()), sender=ba.verifying_key)
        new_block_notif = NewBlockNotification.create(
            block_hash=ba.curr_block_hash,
            merkle_roots=[RESULT_HASH1],
            prev_block_hash=old_b_hash,
            masternode_signature=signature,
            input_hashes=[INPUT_HASH1]
        )
        ba.pub.send_msg.assert_called_with(msg=new_block_notif, header=DEFAULT_FILTER.encode())

    @BlockAggTester.test
    @mock.patch("cilantro.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 2)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
    def test_combine_result_hash_with_multiple_sb(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()
        ba.pub = MagicMock()
        old_b_hash = ba.curr_block_hash

        # Sub block 0
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0)
            ba.recv_sub_block_contender(sbc)

        # Sub block 1
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH2), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH2, INPUT_HASH2, MERKLE_LEAVES2, signature, TXS2, 0)
            ba.recv_sub_block_contender(sbc)

        signature = MerkleSignature.create(sig_hex=wallet.sign(TEST_SK, ba.curr_block_hash.encode()), timestamp=str(time.time()), sender=ba.verifying_key)
        new_block_notif = NewBlockNotification.create(
            block_hash=ba.curr_block_hash,
            merkle_roots=[RESULT_HASH1, RESULT_HASH2],
            prev_block_hash=old_b_hash,
            masternode_signature=signature,
            input_hashes=[INPUT_HASH1, INPUT_HASH2]
        )
        ba.pub.send_msg.assert_called_with(msg=new_block_notif, header=DEFAULT_FILTER.encode())

    @BlockAggTester.test
    @mock.patch("cilantro.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 2)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
    def test_combine_result_hash_with_multiple_sb_with_extras(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()
        ba.pub = MagicMock()
        old_b_hash = ba.curr_block_hash

        # Sub block 0
        for i in range(NUM_DELEGATES):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0)
            ba.recv_sub_block_contender(sbc)

        # Sub block 1
        for i in range(NUM_DELEGATES):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH2), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH2, INPUT_HASH2, MERKLE_LEAVES2, signature, TXS2, 1)
            ba.recv_sub_block_contender(sbc)

        signature = MerkleSignature.create(sig_hex=wallet.sign(TEST_SK, ba.curr_block_hash.encode()), timestamp=str(time.time()), sender=ba.verifying_key)
        new_block_notif = NewBlockNotification.create(
            block_hash=ba.curr_block_hash,
            merkle_roots=[RESULT_HASH1, RESULT_HASH2],
            prev_block_hash=old_b_hash,
            masternode_signature=signature,
            input_hashes=[INPUT_HASH1, INPUT_HASH2]
        )
        ba.pub.send_msg.assert_called_with(msg=new_block_notif, header=DEFAULT_FILTER.encode())

    @BlockAggTester.test
    @mock.patch("cilantro.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 1)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 1)
    def test_recv_ignore_extra_sub_block_contenders(self, *args):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)
        ba.manager = MagicMock()
        ba.build_task_list()
        bh = ba.curr_block_hash
        for i in range(DELEGATE_MAJORITY + 5):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i%DELEGATE_MAJORITY]['sk'], vk=TESTNET_DELEGATES[i%DELEGATE_MAJORITY]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0)
            ba.recv_sub_block_contender(sbc)

        signature = MerkleSignature.create(sig_hex=wallet.sign(TEST_SK, ba.curr_block_hash.encode()), timestamp=str(time.time()), sender=ba.verifying_key)
        new_block_notif = NewBlockNotification.create(
            block_hash=ba.curr_block_hash,
            merkle_roots=[RESULT_HASH1],
            prev_block_hash=bh,
            masternode_signature=signature,
            input_hashes=[INPUT_HASH1]
        )
        ba.pub.send_msg.assert_called_with(msg=new_block_notif, header=DEFAULT_FILTER.encode())

    @BlockAggTester.test
    @mock.patch("cilantro.nodes.masternode.block_aggregator.MASTERNODE_MAJORITY", 2)
    @mock.patch("cilantro.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 2)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
    def test_recv_result_hash_multiple_subblocks_consensus(self, *args):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)
        ba.manager = MagicMock()
        ba.build_task_list()
        bh = ba.curr_block_hash

        # Sub block 0
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0)
            ba.recv_sub_block_contender(sbc)

        # Sub block 1
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH2), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH2, INPUT_HASH2, MERKLE_LEAVES2, signature, TXS2, 1)
            ba.recv_sub_block_contender(sbc)

        self.assertEqual(len(ba.full_blocks), 1)

        for i in range(2):
            signature = MerkleSignature.create(
                sig_hex=wallet.sign(TESTNET_MASTERNODES[i]['sk'], ba.curr_block_hash.encode()),
                sender=TESTNET_MASTERNODES[i]['vk'])
            new_block_notif = NewBlockNotification.create(
                block_hash=ba.curr_block_hash,
                merkle_roots=[RESULT_HASH1, RESULT_HASH2],
                prev_block_hash=bh,
                masternode_signature=signature,
                input_hashes=[INPUT_HASH1, INPUT_HASH2]
            )
            ba.recv_new_block_notif(new_block_notif)

        self.assertEqual(len(ba.full_blocks[ba.curr_block_hash]['_master_signatures_']), 2)
        self.assertEqual(ba.full_blocks[ba.curr_block_hash]['_block_metadata_'], new_block_notif)

    @BlockAggTester.test
    @mock.patch("cilantro.nodes.masternode.block_aggregator.NUM_SB_PER_BLOCK", 2)
    @mock.patch("cilantro.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
    def test_recv_result_hash_multiple_subblocks(self, *args):

        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)
        ba.manager = MagicMock()
        ba.build_task_list()
        bh = ba.curr_block_hash

        # Sub block 0
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1, 0)
            ba.recv_sub_block_contender(sbc)

        # Sub block 1
        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH2), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH2, INPUT_HASH2, MERKLE_LEAVES2, signature, TXS2, 1)
            ba.recv_sub_block_contender(sbc)

        self.assertEqual(len(ba.sub_blocks), 2)

    @BlockAggTester.test
    def test_combine_result_hash_transactions_missing(self, *args):
        ba = BlockAggregator(ip=TEST_IP, signing_key=TEST_SK)

        ba.manager = MagicMock()
        ba.build_task_list()

        for i in range(DELEGATE_MAJORITY):
            signature = build_test_merkle_sig(msg=bytes.fromhex(RESULT_HASH1), sk=TESTNET_DELEGATES[i]['sk'], vk=TESTNET_DELEGATES[i]['vk'])
            sbc = SubBlockContender.create(RESULT_HASH1, INPUT_HASH1, MERKLE_LEAVES1, signature, TXS1[:3], 0)
            ba.recv_sub_block_contender(sbc)

        self.assertEqual(len(ba.result_hashes[RESULT_HASH1]['_valid_signatures_']), DELEGATE_MAJORITY)
        self.assertEqual(len(ba.result_hashes[RESULT_HASH1]['_transactions_']), 3)
        self.assertEqual(len(ba.full_blocks), 0)


if __name__ == '__main__':
    unittest.main()
