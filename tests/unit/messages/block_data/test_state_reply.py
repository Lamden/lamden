# from cilantro.messages.block_data.state_update import StateUpdateReply
# from cilantro.messages.block_data.block_metadata import BlockMetaData
# from cilantro.messages.block_data.block_data import BlockDataBuilder
# from cilantro.constants.masternode import SUBBLOCKS_REQUIRED
# from unittest import TestCase
# import secrets
#
# # TODO delete this once we remove it from MN
# class StateRequestTest(TestCase):
#
#     def test_init(self):
#         block_data = BlockDataBuilder.create_block(sub_block_count=4)
#
#         sr = StateUpdateReply.create(block_data)
#
#         self.assertEqual(block_data, sr.block_data)
#
#     def test_serialization(self):
#         """
#         Tests serialize and from_bytes are inverse operations
#         """
#         block_data = BlockDataBuilder.create_block(sub_block_count=4)
#
#         sr = StateUpdateReply.create(block_data)
#         sr_bin = sr.serialize()
#
#         sr_clone = StateUpdateReply.from_bytes(sr_bin)
#
#         self.assertEqual(sr, sr_clone)
