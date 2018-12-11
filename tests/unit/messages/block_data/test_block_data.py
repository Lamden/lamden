from cilantro.messages.transaction.data import TransactionData
from cilantro.messages.transaction.contract import ContractTransactionBuilder, ContractTransaction
from cilantro.messages.block_data.block_data import BlockData, GENESIS_BLOCK_HASH
from cilantro.protocol.structures.merkle_tree import MerkleTree
from unittest import TestCase
import unittest
from cilantro.constants.testnet import TESTNET_MASTERNODES
TEST_SK, TEST_VK = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']


class TestBlockData(TestCase):

    def test_create(self):
        txs = []
        for _ in range(8):
            txs.append(TransactionData.create(
                contract_tx=ContractTransactionBuilder.create_currency_tx(
                    sender_sk=TEST_SK, receiver_vk='A' * 64, amount=10),
                status='SUCCESS', state='SET x 1'))
        txs_bin = [tx.serialize() for tx in txs]

        prev_b_hash = GENESIS_BLOCK_HASH
        merkle_roots = [MerkleTree.from_raw_transactions(txs_bin[:4]).root_as_hex,
                        MerkleTree.from_raw_transactions(txs_bin[4:]).root_as_hex]
        input_hashes = ['A'*64, 'B'*64]
        block_hash = BlockData.compute_block_hash(merkle_roots, prev_b_hash)
        block_num = 1
        block_owners = [TEST_VK]

        block = BlockData.create(block_hash=block_hash, prev_block_hash=prev_b_hash, transactions=txs,
                                 block_owners=block_owners, merkle_roots=merkle_roots, input_hashes=input_hashes,
                                 block_num=block_num)

        self.assertEqual(block.block_hash, block_hash)
        self.assertEqual(block.input_hashes, input_hashes)
        self.assertEqual(block.merkle_roots, merkle_roots)
        self.assertEqual(block.block_num, block_num)
        self.assertEqual(block.block_owners, block_owners)
        self.assertEqual(block.transactions, txs)
        self.assertEqual(block.prev_block_hash, prev_b_hash)

    def test_serialize_deserialize(self):
        txs = []
        for _ in range(8):
            txs.append(TransactionData.create(
                contract_tx=ContractTransactionBuilder.create_currency_tx(
                    sender_sk=TEST_SK, receiver_vk='A' * 64, amount=10),
                status='SUCCESS', state='SET x 1'))
        txs_bin = [tx.serialize() for tx in txs]

        prev_b_hash = GENESIS_BLOCK_HASH
        merkle_roots = [MerkleTree.from_raw_transactions(txs_bin[:4]).root_as_hex,
                        MerkleTree.from_raw_transactions(txs_bin[4:]).root_as_hex]
        input_hashes = ['A'*64, 'B'*64]
        block_hash = BlockData.compute_block_hash(merkle_roots, prev_b_hash)
        block_num = 1
        block_owners = [TEST_VK]

        block = BlockData.create(block_hash=block_hash, prev_block_hash=prev_b_hash, transactions=txs,
                                 block_owners=block_owners, merkle_roots=merkle_roots, input_hashes=input_hashes,
                                 block_num=block_num)
        clone = BlockData.from_bytes(block.serialize())

        self.assertEqual(clone, block)


if __name__ == '__main__':
    unittest.main()
