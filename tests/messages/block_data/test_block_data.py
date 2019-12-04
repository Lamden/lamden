from cilantro_ee.messages.transaction.data import TransactionData
from cilantro_ee.utils import Hasher
from cilantro_ee.messages.transaction.contract import ContractTransactionBuilder, ContractTransaction
from cilantro_ee.messages.block_data.block_data import BlockData, GENESIS_BLOCK_HASH, BlockDataBuilder
from cilantro_ee.messages.block_data.state_update import BlockDataReply
from cilantro_ee.messages.block_data.sub_block import SubBlock, SubBlockBuilder
from cilantro_ee.core.containers.merkle_tree import MerkleTree
from unittest import TestCase
import unittest
from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
TEST_SK, TEST_VK = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']


class TestBlockData(TestCase):

    def test_create(self):
        input_hash1 = 'A'*64
        input_hash2 = 'B'*64
        sb1 = SubBlockBuilder.create(input_hash=input_hash1, idx=0)
        sb2 = SubBlockBuilder.create(input_hash=input_hash2, idx=1)
        sbs = [sb1, sb2]

        prev_b_hash = GENESIS_BLOCK_HASH
        block_hash = BlockData.compute_block_hash([sb1.merkle_root, sb2.merkle_root], prev_b_hash)
        block_num = 1
        block_owners = [TEST_VK]

        block = BlockData.create(block_hash=block_hash, prev_block_hash=prev_b_hash, block_num=block_num,
                                 sub_blocks=sbs, block_owners=block_owners)

        self.assertEqual(block.block_hash, block_hash)
        self.assertEqual(block.block_num, block_num)
        self.assertEqual(block.block_owners, block_owners)
        self.assertEqual(block.prev_block_hash, prev_b_hash)

        self.assertEqual(block.transactions, sb1.transactions + sb2.transactions)
        self.assertEqual(block.merkle_roots, [sb1.merkle_root, sb2.merkle_root])
        self.assertEqual(block.input_hashes, [sb1.input_hash, sb2.input_hash])
        self.assertEqual(block.merkle_leaves, sb1.merkle_leaves + sb2.merkle_leaves)

    def test_serialize_deserialize(self):
        input_hash1 = 'A'*64
        input_hash2 = 'B'*64
        sb1 = SubBlockBuilder.create(input_hash=input_hash1, idx=0)
        sb2 = SubBlockBuilder.create(input_hash=input_hash2, idx=1)
        sbs = [sb1, sb2]

        prev_b_hash = GENESIS_BLOCK_HASH
        block_hash = BlockData.compute_block_hash([sb1.merkle_root, sb2.merkle_root], prev_b_hash)
        block_num = 1
        block_owners = [TEST_VK]

        block = BlockData.create(block_hash=block_hash, prev_block_hash=prev_b_hash, block_num=block_num,
                                 sub_blocks=sbs, block_owners=block_owners)

        clone = BlockData.from_bytes(block.serialize())
        self.assertEqual(clone, block)

    def test_get_tx_hash_to_merkle_leaf(self):
        input_hash1 = 'A'*64
        input_hash2 = 'B'*64
        sb1 = SubBlockBuilder.create(input_hash=input_hash1, idx=0)
        sb2 = SubBlockBuilder.create(input_hash=input_hash2, idx=1)
        sbs = [sb1, sb2]

        prev_b_hash = GENESIS_BLOCK_HASH
        block_hash = BlockData.compute_block_hash([sb1.merkle_root, sb2.merkle_root], prev_b_hash)
        block_num = 1
        block_owners = [TEST_VK]

        block = BlockData.create(block_hash=block_hash, prev_block_hash=prev_b_hash, block_num=block_num,
                                 sub_blocks=sbs, block_owners=block_owners)

        tx_hash_to_leaves = block.get_tx_hash_to_merkle_leaf()

        # Make sure lengths match up
        self.assertEqual(len(block.merkle_leaves), len(tx_hash_to_leaves))

    def test_block_data_builder(self):
        data = BlockDataBuilder.create_random_block(prev_hash=GENESIS_BLOCK_HASH, num=1)
        self.assertEqual(data.prev_block_hash, GENESIS_BLOCK_HASH)
        self.assertEqual(data.block_num, 1)

    def test_block_data_builder_conseq_blocks(self):
        num = 5
        blocks = BlockDataBuilder.create_conseq_blocks(num)
        curr_hash, curr_num = GENESIS_BLOCK_HASH, 0
        for block in blocks:
            self.assertEqual(block.prev_block_hash, curr_hash)
            self.assertEqual(block.block_num, curr_num+1)
            curr_hash = block.block_hash
            curr_num += 1

    def test_block_data_reply_create_from_block(self):
        block = BlockDataBuilder.create_random_block()
        bd_reply = BlockDataReply.create_from_block(block)

        self.assertEqual(block.block_hash, bd_reply.block_hash)
        self.assertEqual(block.block_num, bd_reply.block_num)
        self.assertEqual(block.block_owners, bd_reply.block_owners)
        self.assertEqual(block.prev_block_hash, bd_reply.prev_block_hash)
        self.assertEqual(block.transactions, bd_reply.transactions)

    def test_from_dict(self):
        block = BlockDataBuilder.create_random_block()
        clone_from_bytes = BlockData.from_bytes(block.serialize())
        clone_from_dict = BlockData.from_dict(block.to_dict())
        clone_from_bytes_to_dict = BlockData.from_dict(clone_from_bytes.to_dict())

        self.assertEqual(block, clone_from_bytes)
        self.assertEqual(clone_from_bytes, clone_from_dict)
        self.assertEqual(clone_from_dict, clone_from_bytes_to_dict)


if __name__ == '__main__':
    unittest.main()
