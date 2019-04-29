import unittest
from unittest import TestCase
from unittest.mock import patch
#from cilantro_ee.messages.block_data.sub_block import SubBlock, SubBlockBuilder
from cilantro_ee.storage.mongo import MDB
from cilantro_ee.storage.mn_api import StorageDriver
from cilantro_ee.nodes.masternode.master_store import MasterOps
import cilantro_ee.nodes.masternode.webserver as endpt

from cilantro_ee.messages.block_data.block_data import *


TEST_IP = '127.0.0.1'
MN_SK = TESTNET_MASTERNODES[0]['sk']
MN_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_DELEGATES[0]['vk']


class TestStorageDriver(TestCase):

    @classmethod
    def setUpClass(cls):
        MasterOps.init_master(key = MN_SK)
        #cls.driver = StorageDriver()

    def setUp(self):
        MDB.reset_db()

    def test_init(self):
        """
        verifies genesis block and get_full_blk api
        :return:
        """
        blk_frm_num = MasterOps.get_full_blk(blk_num = 0)
        blk_frm_hash = MasterOps.get_full_blk(blk_hash = "0000000000000000000000000000000000000000000000000000000000000000")
        self.assertEqual(blk_frm_num.get("blockNum"), 0)
        self.assertEqual(blk_frm_hash.get("blockNum"), 0)

    def test_store_blks(self):
        """
        Verifies api's
        - store_block
        :return:
        """

        blocks = BlockDataBuilder.create_conseq_blocks(5)
        for block in blocks:
            StorageDriver.store_block(block.sub_blocks)

        blk_idx_3 = MasterOps.get_blk_idx(n_blks = 3)
        self.assertEqual(len(blk_idx_3), 3)
        self.assertEqual(blk_idx_3[0].get('blockNum'), 5)

        last_blk_num = StorageDriver.get_latest_block_num()
        last_blk_hash = StorageDriver.get_latest_block_hash()

        fifth_block = StorageDriver.get_nth_full_block(given_bnum = 5)

        self.assertEqual(last_blk_num, fifth_block.get('blockNum'))
        self.assertEqual(last_blk_hash, fifth_block.get('blockHash'))


    # @patch('cilantro_ee.nodes.masternode.webserver.get')
    # def test_webserver_api(self):
    #     blocks = BlockDataBuilder.create_conseq_blocks(5)
    #     for block in blocks:
    #         StorageDriver.store_block(block.sub_blocks)
    #
    #     json_blk = endpt._respond_to_request(blocks[2])
    #     print(json_blk)




    # @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
    # def test_store_block(self):
    #     sub_blocks = [SubBlockBuilder.create(idx=i) for i in range(2)]
    #     block = self.driver.store_block(sub_blocks)
    #     last_stored_hash = self.driver.get_latest_block_hash()
    #
    #     tx = sub_blocks[1].transactions[0].transaction
    #     usr_tx_hash = Hasher.hash(tx)
    #     result = self.driver.get_transactions(raw_tx_hash = usr_tx_hash)
    #
    #     self.assertEqual(block.block_num, 1)
    #     self.assertEqual(block.block_hash, last_stored_hash)
    #     self.assertTrue(result)

    # @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
    # def test_get_latest_blocks(self):
    #     blocks = []
    #     for i in range(5):
    #         if len(blocks) > 0:
    #             block = BlockDataBuilder.create_block(prev_block_hash=blocks[-1].block_hash, blk_num=len(blocks)+1)
    #         else:
    #             block = BlockDataBuilder.create_block()
    #         blocks.append(block)
    #         self.driver.store_block(block, validate=False)
    #     latest_blocks = self.driver.get_latest_blocks(blocks[1].block_hash)
    #     self.assertEqual(len(latest_blocks), 3)
    #     self.assertEqual(latest_blocks[0].block_hash, blocks[2].block_hash)
    #     self.assertEqual(latest_blocks[1].block_hash, blocks[3].block_hash)
    #     self.assertEqual(latest_blocks[2].block_hash, blocks[4].block_hash)


if __name__ == '__main__':
    unittest.main()
