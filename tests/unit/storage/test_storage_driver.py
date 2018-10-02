import unittest
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES
from cilantro.storage.driver import StorageDriver
from cilantro.storage.sqldb import SQLDB
from cilantro.messages.block_data.block_data import BlockData, BlockDataBuilder
from cilantro.utils.hasher import Hasher
from cilantro.messages.consensus.sub_block_contender import SubBlockContenderBuilder
from cilantro.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig

TEST_IP = '127.0.0.1'
MN_SK = TESTNET_MASTERNODES[0]['sk']
MN_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_DELEGATES[0]['vk']


class TestStorageDriver(TestCase):

    @classmethod
    def setUpClass(cls):
        SQLDB.force_start()
        SQLDB.reset_db()

    @classmethod
    def tearDownClass(cls):
        SQLDB.connection.close()

    def setUp(self):
        SQLDB.truncate_tables('sub_block', 'block', 'transaction')

    @mock.patch("cilantro.constants.system_config.NUM_SUB_BLOCKS", 2)
    def test_store_block(self):
        block = BlockDataBuilder.create_block()
        StorageDriver.store_block(block, validate=False)
        block_meta = StorageDriver.get_block_meta(block.block_hash)
        self.assertEqual(block_meta['block_num'], 1)
        self.assertEqual(block_meta['block_hash'], block.block_hash)
        self.assertEqual(block_meta['merkle_roots'], block.merkle_roots)
        self.assertEqual(block_meta['prev_block_hash'], block.prev_block_hash)
        self.assertEqual(block_meta['masternode_signature'], block.masternode_signature)

    def test_store_sub_block(self):
        sub_block = SubBlockContenderBuilder.create()
        signatures = [build_test_merkle_sig() for _ in range(len(sub_block.merkle_leaves))]
        StorageDriver.store_sub_block(sub_block, signatures)
        sub_block_meta = StorageDriver.get_sub_block_meta(sub_block.result_hash)
        self.assertEqual(sub_block_meta['merkle_root'], sub_block.result_hash)
        self.assertEqual(sub_block_meta['signatures'], signatures)
        self.assertEqual(sub_block_meta['merkle_leaves'], sub_block.merkle_leaves)
        self.assertEqual(sub_block_meta['sb_index'], sub_block.sb_index)

    @mock.patch("cilantro.constants.system_config.NUM_SUB_BLOCKS", 2)
    def test_get_transactions_by_block_hash(self):
        block = BlockDataBuilder.create_block()
        StorageDriver.store_block(block, validate=False)
        txs = StorageDriver.get_transactions(block_hash=block.block_hash)
        self.assertEqual(
            set([tx.contract_tx.serialize() for tx in block.transactions]),
            set([tx['contract_tx'].serialize() for tx in txs])
        )

if __name__ == '__main__':
    unittest.main()
