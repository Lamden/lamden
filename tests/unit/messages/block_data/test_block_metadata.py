"""
BlockMetaData is just a subclass of BlockData, with no additional fields, so tests should be covered by test_block_data

-- davis
"""

# from unittest import TestCase
# from unittest import mock
#
# from cilantro_ee.core.crypto import wallet
# from cilantro_ee.messages.block_data.block_data import BlockData
# from cilantro_ee.messages.consensus.merkle_signature import MerkleSignature
#
# from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
# TEST_SK, TEST_VK = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']
#
#
# class TestBlockMetaData(TestCase):
#
#     @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
#     def test_create(self):
#         from cilantro_ee.messages.block_data.block_metadata import BlockMetaData  # avoid cyclic imports
#
#         prev_b_hash = 'A' * 64
#         input_hashes = ['B' * 64, 'C' * 64]
#         roots = ['D' * 64, 'E' * 64]
#         timestamp = 1337
#         block_num = 12
#         b_hash = BlockData.compute_block_hash(sbc_roots=roots, prev_block_hash=prev_b_hash)
#
#         block_owners = [TEST_VK]
#
#         block_meta = BlockMetaData.create(block_hash=b_hash, merkle_roots=roots, input_hashes=input_hashes,
#                                           prev_block_hash=prev_b_hash, block_owners=block_owners, timestamp=timestamp,
#                                           block_num=block_num)
#
#         self.assertEqual(block_meta.prev_block_hash, prev_b_hash)
#         self.assertEqual(block_meta.input_hashes, input_hashes)
#         self.assertEqual(block_meta.merkle_roots, roots)
#         self.assertEqual(block_meta.timestamp,timestamp)
#         self.assertEqual(block_meta.block_hash, b_hash)
#         self.assertEqual(block_meta.block_num, block_num)
#         self.assertEqual(block_meta.block_owners, block_owners)
#
#     @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
#     def test_clone(self):
#         from cilantro_ee.messages.block_data.block_metadata import BlockMetaData  # avoid cyclic imports
#
#         prev_b_hash = 'A' * 64
#         input_hashes = ['B' * 64, 'C' * 64]
#         roots = ['D' * 64, 'E' * 64]
#         timestamp = 1337
#         block_num = 12
#         b_hash = BlockData.compute_block_hash(sbc_roots=roots, prev_block_hash=prev_b_hash)
#
#         block_owners = [TEST_VK]
#
#         block_meta = BlockMetaData.create(block_hash=b_hash, merkle_roots=roots, input_hashes=input_hashes,
#                                           prev_block_hash=prev_b_hash, block_owners=block_owners, timestamp=timestamp,
#                                           block_num=block_num)
#         clone = BlockMetaData.from_bytes(block_meta.serialize())
#
#         self.assertEqual(block_meta, clone)
#
#     @mock.patch("cilantro_ee.messages.block_data.block_metadata.NUM_SB_PER_BLOCK", 2)
#     def test_from_block_data(self):
#         # TODO implement
#         pass


