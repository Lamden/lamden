from unittest import TestCase
from unittest.mock import MagicMock
from cilantro import Constants
from cilantro.db.blocks import *
from cilantro.db import reset_db
from cilantro.messages.consensus.block_contender import build_test_contender
from cilantro.messages.transaction.base import build_test_transaction
from cilantro.utils import Hasher, int_to_bytes
from cilantro.protocol.structures.merkle_tree import MerkleTree
from cilantro.protocol.wallets import ED25519Wallet
import secrets
import random
import time


class TestBlockStorageDriver(TestCase):

    # def setUp(self):
    #     reset_db()

    def _build_valid_block_data(self, num_transactions=4) -> dict:
        """
        Utility method to build a dictionary with all the params needed to invoke store_block
        :param num_transactions:
        :return:
        """
        mn_sk = Constants.Testnet.Masternodes[0]['sk']
        mn_vk = ED25519Wallet.get_vk(mn_sk)
        timestamp = 9000

        raw_transactions = [build_test_transaction().serialize() for _ in range(num_transactions)]

        tree = MerkleTree(raw_transactions)
        merkle_leaves = tree.leaves_as_concat_hex_str
        merkle_root = tree.root_as_hex

        bc = build_test_contender(tree=tree)

        prev_block_hash = '0' * 64

        mn_sig = ED25519Wallet.sign(mn_sk, tree.root)

        return {
            'prev_block_hash': prev_block_hash,
            'block_contender': bc,
            'merkle_leaves': merkle_leaves,
            'merkle_root': merkle_root,
            'masternode_signature': mn_sig,
            'masternode_vk': mn_vk,
            'timestamp': timestamp
        }

    def test_build_valid_block_data_params(self):
        """
        Since _build_valid_block_data relies on lot of other API, we make include this isolated test to make it clear
        if something blows up in _build_valid_block_data
        """
        # We just want to know if any of these calls blows up (i.e. raises any exceptions)
        data = self._build_valid_block_data()
        data2 = self._build_valid_block_data(num_transactions=5)  # try with an odd # of transactions

    def test_store_block_data_invalid_sk(self):
        raw_txs = [secrets.token_bytes(16) for _ in range(16)]
        tree = MerkleTree(leaves=raw_txs)

        bc = build_test_contender(tree=tree)
        bad_sk = 'X' * 128
        timestamp = 9000

        self.assertRaises(AssertionError, BlockStorageDriver.store_block, block_contender=bc, raw_transactions=raw_txs,
                          publisher_sk=bad_sk, timestamp=timestamp)

    def test_get_latest_block_hash(self):
        reset_db()

        first_hash = BlockStorageDriver._get_latest_block_hash()

        # We reset the DB, so the latest hash we pull should be the genesis hash
        self.assertEqual(first_hash, GENESIS_HASH)

    def test_validate_block_data_valid(self):
        block_data = self._build_valid_block_data()
        BlockStorageDriver._validate_block_data(block_data)  # This should not raise any Exceptions

    def test_validate_block_data_missing_keys(self):
        block_data = {
            'block_contender': None,
            'timestamp': None,
            'merkle_root': None,
            'merkle_leaves': None,
            'prev_block_hash': None,
            'masternode_signature': None,
            # 'masternode_vk': None,  # This key is missing
        }
        self.assertRaises(BlockStorageValidationException, BlockStorageDriver._validate_block_data, block_data)

        block_data = {
            'block_contender': None,
            'timestamp': None,
            'merkle_root': None,
            # 'merkle_leaves': None,  # This key is missing
            'prev_block_hash': None,
            'masternode_signature': None,
            'masternode_vk': None,
        }
        self.assertRaises(BlockStorageValidationException, BlockStorageDriver._validate_block_data, block_data)

    def test_validate_block_data_extra_keys(self):
        block_data = {
            'block_contender': None,
            'timestamp': None,
            'merkle_root': None,
            'merkle_leaves': None,
            'prev_block_hash': None,
            'masternode_signature': None,
            'masternode_vk': None,
            'AN EXTRA KEY': None,
            'ANOTHER ONE!': None,
        }
        self.assertRaises(BlockStorageValidationException, BlockStorageDriver._validate_block_data, block_data)

    def test_validate_block_data_invalid_merkle(self):
        block_data = {
            'block_contender': None,
            'timestamp': None,
            'merkle_root': 'A' * 64,
            'merkle_leaves': 'B' * 256,
            'prev_block_hash': None,
            'masternode_signature': None,
            'masternode_vk': None,
        }
        self.assertRaises(InvalidMerkleTreeException, BlockStorageDriver._validate_block_data, block_data)

    def test_validate_block_data_invalid_contender_signatures(self):
        block_data = self._build_valid_block_data()

        bad_contender = MagicMock(spec=BlockContender)
        bad_contender.validate_signatures = MagicMock(return_value=False)

        block_data['block_contender'] = bad_contender

        self.assertRaises(InvalidBlockContenderException, BlockStorageDriver._validate_block_data, block_data)

    def test_validate_block_data_invalid_contender_leaves_length(self):
        bd = self._build_valid_block_data()

        # Create a sketch block contender with the incorrect number of merkle leaves
        bc = bd['block_contender']
        sketch_bc = BlockContender.create(signatures=bc.signatures, merkle_leaves=['0' * 64 for _ in range(27)])

        bd['block_contender'] = sketch_bc

        self.assertRaises(InvalidBlockContenderException, BlockStorageDriver._validate_block_data, bd)

    def test_validate_block_data_invalid_contender_leaves_mismatch(self):
        bd = self._build_valid_block_data(4)

        # Create a sketch block contender with leaves that are different from the merkle leaves in the block_data
        raw_transactions = [build_test_transaction().serialize() for _ in range(4)]
        tree = MerkleTree(raw_transactions)
        sketch_bc = build_test_contender(tree=tree)

        bd['block_contender'] = sketch_bc

        self.assertRaises(InvalidBlockContenderException, BlockStorageDriver._validate_block_data, bd)

    def test_validate_block_data_invalid_signature(self):
        block_data = self._build_valid_block_data()
        block_data['masternode_signature'] = 'A' * 128

        self.assertRaises(InvalidBlockSignatureException, BlockStorageDriver._validate_block_data, block_data)

    def test_compute_block_hash(self):
        # NOTE -- this implicitly tests Hasher.hash_iterable
        bd = self._build_valid_block_data()

        # Correct order of keys should be:
        # ['block_contender',
        #  'masternode_signature',
        #  'masternode_vk',
        #  'merkle_leaves',
        #  'merkle_root',
        #  'prev_block_hash',
        #  'timestamp']

        binary_data = bd['block_contender'].serialize()
        binary_data += bd['masternode_signature'].encode()
        binary_data += bd['masternode_vk'].encode()
        binary_data += bd['merkle_leaves'].encode()
        binary_data += bd['merkle_root'].encode()
        binary_data += bd['prev_block_hash'].encode()
        binary_data += int_to_bytes(bd['timestamp'])

        expected_hash = Hasher.hash(binary_data)
        actual_hash = BlockStorageDriver._compute_block_hash(bd)

        self.assertEqual(expected_hash, actual_hash)

    def test_store_block_inserts(self):
        reset_db()

        with DB() as db:
            initial_num_blocks = len(db.tables.blocks.select().run(db.ex))

        mn_sk = Constants.Testnet.Masternodes[0]['sk']
        timestamp = random.randint(0, pow(2, 32))
        raw_transactions = [build_test_transaction().serialize() for _ in range(19)]

        tree = MerkleTree(raw_transactions)
        bc = build_test_contender(tree=tree)

        BlockStorageDriver.store_block(block_contender=bc, raw_transactions=raw_transactions, publisher_sk=mn_sk, timestamp=timestamp)

        with DB() as db:
            blocks = db.tables.blocks.select().run(db.ex)
            self.assertEquals(len(blocks) - initial_num_blocks, 1)
            self.assertEquals(blocks[-1]['timestamp'], timestamp)

    def test_retrieve_block_invalid_args(self):
        self.assertRaises(AssertionError, BlockStorageDriver.retrieve_block, )
        self.assertRaises(AssertionError, BlockStorageDriver.retrieve_block, number=-10)
        self.assertRaises(AssertionError, BlockStorageDriver.retrieve_block, hash='not valid hex')
        self.assertRaises(AssertionError, BlockStorageDriver.retrieve_block, hash='aabbccddeeff0011')

    def test_retrieve_block_by_number(self):
        genesis = BlockStorageDriver.retrieve_block(number=1)

        self.assertTrue(genesis)
        self.assertEquals(genesis['number'], 1)
        self.assertEquals(genesis['hash'], GENESIS_HASH)
        self.assertEquals(genesis['timestamp'], GENESIS_TIMESTAMP)
        self.assertEquals(genesis['block_contender'], GENESIS_BLOCK_CONTENDER)

    def test_retrieve_block_by_number_doesnt_exist(self):
        block = BlockStorageDriver.retrieve_block(number=90000)
        self.assertFalse(block)

    def test_retrieve_block_by_hash(self):
        genesis = BlockStorageDriver.retrieve_block(hash=GENESIS_HASH)

        self.assertEquals(genesis['number'], 1)
        self.assertEquals(genesis['hash'], GENESIS_HASH)
        self.assertEquals(genesis['timestamp'], GENESIS_TIMESTAMP)

    def test_retrieve_block_by_hash_doesnt_exist(self):
        block = BlockStorageDriver.retrieve_block(hash='A' * 64)
        self.assertFalse(block)

    def test_retrieve_latest_inserted(self):
        mn_sk = Constants.Testnet.Masternodes[0]['sk']
        timestamp = random.randint(0, pow(2, 32))
        raw_transactions = [build_test_transaction().serialize() for _ in range(19)]

        tree = MerkleTree(raw_transactions)
        bc = build_test_contender(tree=tree)

        BlockStorageDriver.store_block(block_contender=bc, raw_transactions=raw_transactions, publisher_sk=mn_sk, timestamp=timestamp)

        latest = BlockStorageDriver.retrieve_latest_block()

        self.assertTrue(latest)
        self.assertEquals(latest['timestamp'], timestamp)
        self.assertEquals(latest['block_contender'], bc)

    def test_encode_decode_block(self):
        block_data = self._build_valid_block_data()
        clone = BlockStorageDriver._decode_block(BlockStorageDriver._encode_block(block_data))
        self.assertEquals(block_data, clone)

    def test_validate_block_link(self):
        # TODO implement
        pass

    def test_validate_block_link_invalid_block_data(self):
        bd1 = self._build_valid_block_data()
        bd1['hash'] = BlockStorageDriver._compute_block_hash(bd1)
        bd1['number'] = 2

        bd2 = self._build_valid_block_data()
        bd2['prev_block_hash'] = bd1['hash']
        bd2['hash'] = BlockStorageDriver._compute_block_hash(bd2)
        bd2['number'] = 3

        # Muck up Merkle tree so _validate_block_data should fail
        for bd in (bd1, bd2):
            bd['merkle_root'] = 'AB' * 32

        self.assertRaises(InvalidMerkleTreeException, BlockStorageDriver._validate_block_link, bd1, bd2)

    def test_validate_block_link_invalid_block_hash(self):
        bd1 = self._build_valid_block_data()
        bd1['hash'] = BlockStorageDriver._compute_block_hash(bd1)
        bd1['number'] = 2

        bd2 = self._build_valid_block_data()
        bd2['prev_block_hash'] = bd1['hash']
        bd2['hash'] = 'A' * 64  # intentionally not BlockStorageDriver._compute_block_hash(bd2)
        bd2['number'] = 3

        self.assertRaises(InvalidBlockHashException, BlockStorageDriver._validate_block_link, bd1, bd2)

    def test_validate_block_link_invalid_block_linkage(self):
        bd1 = self._build_valid_block_data()
        bd1['hash'] = BlockStorageDriver._compute_block_hash(bd1)
        bd1['number'] = 2

        bd2 = self._build_valid_block_data()
        bd2['prev_block_hash'] = 'A' * 64  # something that obviously not the parent block's hash
        bd2['hash'] = BlockStorageDriver._compute_block_hash(bd2)
        bd2['number'] = 3

        self.assertRaises(InvalidBlockLinkException, BlockStorageDriver._validate_block_link, bd1, bd2)

    def test_validate_blockchain(self):
        reset_db()

        # Stuff a bunch of blocks in
        for _ in range(4):
            mn_sk = Constants.Testnet.Masternodes[0]['sk']
            timestamp = random.randint(0, pow(2, 32))
            raw_transactions = [build_test_transaction().serialize() for _ in range(19)]

            tree = MerkleTree(raw_transactions)
            bc = build_test_contender(tree=tree)

            BlockStorageDriver.store_block(block_contender=bc, raw_transactions=raw_transactions, publisher_sk=mn_sk,
                                           timestamp=timestamp)

        # This should not blow up
        BlockStorageDriver.validate_blockchain()

        print("THIS TEST SHOULD FUCKING RETURN NOW")

    # def test_validate_blockchain_invalid(self):
    #     # TODO implement
    #     pass
    #
    # def test_super_test(self):
    #     """
    #     This test does way to much but ay that's the point of a super test
    #     """
    #     # TODO implement
    #     pass

