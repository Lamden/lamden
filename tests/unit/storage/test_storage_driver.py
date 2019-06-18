import unittest
from unittest import TestCase
from unittest.mock import patch
#from cilantro_ee.messages.block_data.sub_block import SubBlock, SubBlockBuilder
from cilantro_ee.storage.mongo import MDB
from cilantro_ee.storage.mn_api import StorageDriver
from cilantro_ee.nodes.masternode.master_store import MasterOps, GlobalColdStorage
import cilantro_ee.nodes.masternode.webserver as endpt

from cilantro_ee.messages.block_data.block_data import *


TEST_IP = '127.0.0.1'
MN_SK = TESTNET_MASTERNODES[0]['sk']
MN_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_DELEGATES[0]['vk']


def create_random_block(cls, prev_hash: str=GENESIS_BLOCK_HASH, num: int=1) -> BlockData:
    from cilantro_ee.messages.block_data.sub_block import SubBlockBuilder

    input_hash1 = 'A'*64
    input_hash2 = 'B'*64
    sb1 = SubBlockBuilder.create(input_hash=input_hash1, idx=0)
    sb2 = SubBlockBuilder.create(input_hash=input_hash2, idx=1)
    sbs = [sb1, sb2]

    block_hash = BlockData.compute_block_hash([sb1.merkle_root, sb2.merkle_root], prev_hash)
    block_num = num
    block_owners = [m['vk'] for m in TESTNET_MASTERNODES]  #[cls.MN_VK]

    block = BlockData.create(block_hash=block_hash, prev_block_hash=prev_hash, block_num=block_num,
                             sub_blocks=sbs, block_owners=block_owners)

    return block


def create_conseq_blocks(cls, num_blocks: int, first_hash=GENESIS_BLOCK_HASH, first_num=1):
    curr_num, curr_hash = first_num, first_hash
    blocks = []
    for _ in range(num_blocks):
        block = cls.create_random_block(curr_hash, curr_num)
        curr_num += 1
        curr_hash = block.block_hash
        blocks.append(block)
    return blocks


class TestStorageDriver(TestCase):

    @classmethod
    def setUpClass(cls):
        MasterOps.init_master(key = MN_SK)

    def setUp(self):
        MDB.reset_db()

    def test_init(self):
        """
        verifies genesis block and get_full_blk api
        :return:
        """
        block_1 = GlobalColdStorage.driver.blocks.collection.find_one({
            'blockNum': 0
        })
        block_2 = GlobalColdStorage.driver.blocks.collection.find_one({
            'blockHash':"0000000000000000000000000000000000000000000000000000000000000000"
        })
        self.assertEqual(block_1.get("blockNum"), 0)
        self.assertEqual(block_2.get("blockNum"), 0)

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

if __name__ == '__main__':
    unittest.main()
