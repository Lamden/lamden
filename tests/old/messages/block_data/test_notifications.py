from cilantro_ee.messages.notification import *
# import unittest
from unittest import TestCase
import hashlib


class TestBlockNotification(TestCase):

    def test_new_block_notification(self):
        block_hash = 'X3' * 32
        block_num = 32
        first_sb_idx = 4
        block_owners = [ "abc", "def", "pqr"]
        input_hashes = ['AB' * 32, 'BC' * 32, 'C'*64, 'D'*64]

        nbn = BlockNotification.get_new_block_notification(block_num=block_num,
                           block_hash=block_hash, block_owners=block_owners,
                           first_sb_idx=first_sb_idx, input_hashes=input_hashes)

        bn = BlockNotification.unpack_block_notification(nbn)
        self.assertEqual(bn.blockNum, block_num)
        self.assertEqual(len(bn.blockOwners), len(block_owners))
        self.assertEqual(bn.type.which(), "newBlock")
        self.assertNotEqual(bn.type.which(), "emptyBlock")

    def test_empty_block_notification(self):
        prev_hash = 'A' * 64
        block_num = 32
        first_sb_idx = 4
        input_hashes = ['AB' * 32, 'BC' * 32, 'C'*64, 'D'*64]

        if type(prev_hash) == str:
            prev_hash = bytes.fromhex(prev_hash)
        h = hashlib.sha3_256()
        h.update(prev_hash)
        for ih in input_hashes:
            if type(ih) == str:
                ih = bytes.fromhex(ih)
            h.update(ih)
        block_hash = h.digest()

        ebn = BlockNotification.get_empty_block_notification(block_num=block_num,
                           block_hash=block_hash,
                           first_sb_idx=first_sb_idx, input_hashes=input_hashes)

        bn = BlockNotification.unpack_block_notification(ebn)
        self.assertEqual(bn.blockNum, block_num)
        self.assertEqual(bn.blockHash, block_hash)
        self.assertEqual(len(bn.blockOwners), 0)
        self.assertNotEqual(bn.type.which(), "newBlock")
        self.assertEqual(bn.type.which(), "emptyBlock")
