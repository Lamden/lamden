from cilantro_ee.messages.block_data.notification import *
# import unittest
from unittest import TestCase


class TestBlockNotification(TestCase):

    def test_create(self):
        prev_hash = 'A' * 64
        block_hash = 'X3' * 32
        block_num = 32
        first_sb_idx = 4
        block_owners = [ "abc", "def", "pqr"]
        input_hashes = ['AB' * 32, 'BC' * 32, 'C'*64, 'D'*64]

        fbn = ConsensusBlockNotification.create(prev_block_hash=prev_hash,
                           block_hash=block_hash, block_num=block_num, first_sb_idx=first_sb_idx,
                           block_owners=block_owners, input_hashes=input_hashes)

        self.assertEqual(fbn.prev_block_hash, prev_hash)
        self.assertEqual(fbn.input_hashes, input_hashes)

    def test_serialize_deserialize(self):
        prev_hash = 'A' * 64
        # block_hash = 'X3' * 32
        # block_num = 32
        # block_owners = [ "abc", "def", "pqr"]

        input_hashes = [['AB' * 32, 'BC' * 32], ['C'*64, 'D'*64], [], ['E'*64]]

        fbn = FailedBlockNotification.create(prev_block_hash=prev_hash, input_hashes=input_hashes)
        clone = FailedBlockNotification.from_bytes(fbn.serialize())

        self.maxDiff = None
        self.assertEqual(clone.input_hashes, input_hashes)
        self.assertEqual(fbn, clone)

