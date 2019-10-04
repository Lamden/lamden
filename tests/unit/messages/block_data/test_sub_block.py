from cilantro_ee.messages.transaction.data import TransactionDataBuilder
from cilantro_ee.messages.block_data.block_data import GENESIS_BLOCK_HASH
from cilantro_ee.core.containers.merkle_tree import MerkleTree
from cilantro_ee.messages.block_data.sub_block import SubBlock, SubBlockBuilder
from cilantro_ee.messages.consensus.merkle_signature import MerkleSignature

from unittest import TestCase
from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
TEST_SK, TEST_VK = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']


class TestSubBlock(TestCase):

    def test_create(self):
        txs = []
        for _ in range(8):
            txs.append(TransactionDataBuilder.create_random_tx())
        txs_bin = [tx.serialize() for tx in txs]

        tree = MerkleTree.from_raw_transactions(txs_bin)
        merkle_root = tree.root_as_hex
        input_hash = 'A'*64
        sb_idx = 0

        sk1, sk2 = 'AB' * 32, 'BC' * 32
        sigs = [MerkleSignature.create_from_payload(sk1, tree.root),
                MerkleSignature.create_from_payload(sk2, tree.root)]

        sb = SubBlock.create(merkle_root=merkle_root, signatures=sigs, merkle_leaves=tree.leaves_as_hex,
                             sub_block_idx=sb_idx, input_hash=input_hash, transactions=txs)

        self.assertEqual(sb.merkle_root, merkle_root)
        self.assertEqual(sb.signatures, sigs)
        self.assertEqual(sb.merkle_leaves, tree.leaves_as_hex)
        self.assertEqual(sb.input_hash, input_hash)
        self.assertEqual(sb.index, sb_idx)
        self.assertEqual(sb.transactions, txs)

    def test_create_no_transactions(self):
        txs = []
        for _ in range(8):
            txs.append(TransactionDataBuilder.create_random_tx())
        txs_bin = [tx.serialize() for tx in txs]

        tree = MerkleTree.from_raw_transactions(txs_bin)
        merkle_root = tree.root_as_hex
        input_hash = 'A'*64
        sb_idx = 0

        sk1, sk2 = 'AB' * 32, 'BC' * 32
        sigs = [MerkleSignature.create_from_payload(sk1, tree.root),
                MerkleSignature.create_from_payload(sk2, tree.root)]

        sb = SubBlock.create(merkle_root=merkle_root, signatures=sigs, merkle_leaves=tree.leaves_as_hex,
                             sub_block_idx=sb_idx, input_hash=input_hash, transactions=[])

        self.assertEqual(sb.merkle_root, merkle_root)
        self.assertEqual(sb.signatures, sigs)
        self.assertEqual(sb.merkle_leaves, tree.leaves_as_hex)
        self.assertEqual(sb.input_hash, input_hash)
        self.assertEqual(sb.index, sb_idx)
        self.assertEqual(sb.transactions, [])

    def test_serialize_deserialize(self):
        sb = SubBlockBuilder.create()
        clone = SubBlock.from_bytes(sb.serialize())
        self.assertEqual(sb, clone)

    def test_remove_tx_data(self):
        sb = SubBlockBuilder.create()

        self.assertTrue(len(sb.transactions) > 0)
        self.assertTrue(len(sb.merkle_leaves) > 0)

        sb.remove_tx_data()

        self.assertTrue(len(sb.transactions) == 0)
        self.assertTrue(len(sb.merkle_leaves) == 0)

    def test_remove_tx_data_from_clone(self):
        sb = SubBlockBuilder.create()
        clone = SubBlock.from_bytes(sb.serialize())

        self.assertTrue(len(clone.transactions) > 0)
        self.assertTrue(len(clone.merkle_leaves) > 0)

        clone.remove_tx_data()

        self.assertTrue(len(clone.transactions) == 0)
        self.assertTrue(len(clone.merkle_leaves) == 0)

    def test_sub_block_builder(self):
        # This shoudl not raise an error
        sb = SubBlockBuilder.create()

