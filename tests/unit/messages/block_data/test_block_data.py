from cilantro.messages.transaction.data import TransactionData
from cilantro.messages.transaction.contract import ContractTransactionBuilder, ContractTransaction
from cilantro.messages.block_data.block_data import BlockData, GENESIS_BLOCK_HASH
from cilantro.messages.block_data.sub_block import SubBlock, SubBlockBuilder
from cilantro.protocol.structures.merkle_tree import MerkleTree
from unittest import TestCase
import unittest
from cilantro.constants.testnet import TESTNET_MASTERNODES
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


if __name__ == '__main__':
    unittest.main()
