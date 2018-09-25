from cilantro.messages.block_data.block_metadata import FullBlockData
from cilantro.utils.test.block_metas import build_valid_block_data
from unittest import TestCase
from cilantro.protocol.structures import MerkleTree
from cilantro.constants.masternode import SUBBLOCKS_REQUIRED
import secrets
import unittest

class TestBlockMetaDataRequest(TestCase):

    def test_create_no_txs(self):
        b_hash = 'AB' * 32
        merkle_roots = ['A' * 64 for _ in range(SUBBLOCKS_REQUIRED)]
        prev_b_hash = 'E' * 64
        mn_sig = 'C' * 128
        timestamp = 9000

        bd = FullBlockData.create(block_hash=b_hash, merkle_roots=merkle_roots, prev_block_hash=prev_b_hash,
                                  timestamp=timestamp, masternode_signature=mn_sig, raw_transactions=None)

        self.assertEqual(bd.block_hash, b_hash)
        self.assertEqual(bd.merkle_roots, merkle_roots)
        self.assertEqual(bd.previous_block_hash, prev_b_hash)
        self.assertEqual(bd.timestamp, timestamp)
        self.assertEqual(bd.transactions, [])

    def test_create_with_tx(self):
        b_hash = 'AB' * 32
        merkle_roots = ['A' * 64 for _ in range(SUBBLOCKS_REQUIRED)]
        prev_b_hash = 'E' * 64
        mn_sig = 'C' * 128
        timestamp = 9000
        txs = [secrets.token_bytes(16) for _ in range(2)]

        bd = FullBlockData.create(block_hash=b_hash, merkle_roots=merkle_roots, prev_block_hash=prev_b_hash,
                                  timestamp=timestamp, masternode_signature=mn_sig, raw_transactions=txs)

        self.assertEqual(bd.block_hash, b_hash)
        self.assertEqual(bd.merkle_roots, merkle_roots)
        self.assertEqual(bd.previous_block_hash, prev_b_hash)
        self.assertEqual(bd.timestamp, timestamp)
        self.assertEqual(bd.raw_transactions, txs)

    def test_serialize_deserialize(self):
        b_hash = 'AB' * 32
        merkle_roots = ['A' * 64 for _ in range(SUBBLOCKS_REQUIRED)]
        prev_b_hash = 'E' * 64
        mn_sig = 'C' * 128
        timestamp = 9000
        txs = [secrets.token_bytes(16) for _ in range(2)]

        bd = FullBlockData.create(block_hash=b_hash, merkle_roots=merkle_roots, prev_block_hash=prev_b_hash,
                                  timestamp=timestamp, masternode_signature=mn_sig, raw_transactions=txs)
        bd_bytes = bd.serialize()
        clone = FullBlockData.from_bytes(bd_bytes)

        self.assertEqual(bd, clone)