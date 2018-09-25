from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig
from unittest import TestCase
import unittest

class TestSubBlockContender(TestCase):
    pass
    # def test_create(self):
    #     result_hash = b'A' * 64
    #     input_hash = b'B' * 64
    #     merkle_leaves = [b'C' * 64] * 5
    #     signature1 = build_test_merkle_sig()
    #     raw_txs1 = [b'1',b'2',b'3',b'4']
    #     sb_index = 0
    #     sbc1 = SubBlockContender.create(result_hash, input_hash, merkle_leaves, sb_index, signature1, raw_txs1)
    #     signature2 = build_test_merkle_sig()
    #     raw_txs2 = [b'1',b'4',b'3',b'5',b'2']
    #     sbc2 = SubBlockContender.create(result_hash, input_hash, merkle_leaves, sb_index, signature2, raw_txs2)
    #     self.assertEqual(sbc1, sbc2)
    #
    # def test_serialize_deserialize(self):
    #     result_hash = b'A' * 64
    #     input_hash = b'B' * 64
    #     merkle_leaves = [b'C' * 64] * 5
    #     signature = build_test_merkle_sig()
    #     raw_txs = [b'1',b'2',b'3',b'4']
    #     sb_index = 0
    #     sbc = SubBlockContender.create(result_hash, input_hash, merkle_leaves, sb_index, signature, raw_txs)
    #     clone = SubBlockContender.from_bytes(sbc.serialize())
    #
    #     self.assertEqual(clone, sbc)

if __name__ == '__main__':
    unittest.main()
