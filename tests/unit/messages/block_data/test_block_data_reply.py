"""
BlockMetaData is just a subclass of BlockData, with no additional fields, so tests should be covered by test_block_data

-- davis
"""


# from cilantro_ee.messages.block_data.state_update import BlockDataReply
# from cilantro_ee.messages.block_data.block_data import BlockDataBuilder
# from cilantro_ee.constants.system_config import NUM_SUB_BLOCKS
# from unittest import TestCase
# import secrets
# from unittest import mock


# BlockDataReply is a subclass of BlockData, with no additions, so test_block_data should cover all the bases here


# class TestBlockDataReply(TestCase):
#
#     def test_init(self):
#         fbmds = [BlockDataBuilder.create_block(blk_num=1, sub_block_count=1) for _ in range(4)]
#
#         sr = BlockDataReply.create(fbmds)
#
#         self.assertEqual(fbmds, sr.block_data)
#
#     def test_serialization(self):
#         """
#         Tests serialize and from_bytes are inverse operations
#         """
#         fbmds = [BlockDataBuilder.create_block(blk_num=1, sub_block_count=1) for _ in range(4)]
#
#         sr = BlockDataReply.create(fbmds)
#         sr_bin = sr.serialize()
#
#         sr_clone = BlockDataReply.from_bytes(sr_bin)
#
#         self.assertEqual(sr, sr_clone)
