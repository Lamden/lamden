import unittest
from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES
from cilantro.storage.driver import StorageDriver
from cilantro.storage.sqldb import SQLDB
from cilantro.messages.block_data.block_data import BlockData, BlockDataBuilder
from cilantro.utils.hasher import Hasher


TEST_IP = '127.0.0.1'
MN_SK = TESTNET_MASTERNODES[0]['sk']
MN_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_DELEGATES[0]['vk']

class TestStorageDriver(TestCase):

    @classmethod
    def setUpClass(cls):
        try: SQLDB.connection.close()
        except: print('Already not connected.')
        SQLDB.force_start()

    @classmethod
    def tearDownClass(cls):
        SQLDB.connection.close()

    def setUp(self):
        SQLDB.truncate_tables('subblock', 'block', 'transaction')

    @mock.patch("cilantro.messages.block_data.block_metadata.SUBBLOCKS_REQUIRED", 2)
    def test_store_block(self):
        block = BlockDataBuilder.create_block()
        StorageDriver.store_block(block, validate=False)
        block_meta = StorageDriver.get_block_meta(block.block_hash)
        self.assertEqual(block_meta.block_num, 1)
        self.assertEqual(block_meta.block_hash, block.block_hash)
        self.assertEqual(block_meta.merkle_roots, block.merkle_roots)
        self.assertEqual(block_meta.prev_block_hash, block.prev_block_hash)
        self.assertEqual(block_meta.masternode_signature, block.masternode_signature)

if __name__ == '__main__':
    unittest.main()
