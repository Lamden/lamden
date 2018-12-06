from cilantro.messages.block_data.state_update import BlockIndexRequest
from unittest import TestCase


class StateRequestTest(TestCase):

    def test_serialization(self):
        """
        Tests serialize and from_bytes are inverse operations
        """
        b_hash = 'A' * 64
        b_num = 1260

        sr = BlockIndexRequest.create(block_num=b_num, block_hash=b_hash)
        sr_bin = sr.serialize()

        sr_clone = BlockIndexRequest.from_bytes(sr_bin)

        self.assertEqual(sr, sr_clone)

    def test_serialization_only_block_num(self):
        """
        Tests serialize and from_bytes are inverse operations, with only the block_num field passed in
        """
        b_num = 1260

        sr = BlockIndexRequest.create(block_num=b_num)
        sr_bin = sr.serialize()

        sr_clone = BlockIndexRequest.from_bytes(sr_bin)

        self.assertEqual(sr, sr_clone)
        self.assertTrue(sr_clone.block_hash is None)
