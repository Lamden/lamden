from cilantro.messages import BlockMetaDataRequest, BlockMetaDataReply, BlockMetaData
from unittest import TestCase


class TestBlockMetaDataRequest(TestCase):

    def test_create(self):
        b_hash = 'A' * 64
        req = BlockMetaDataRequest.create(current_block_hash=b_hash)

        self.assertEquals(req.current_block_hash, b_hash)

    def test_serialize_deserialize(self):
        req = BlockMetaDataRequest.create(current_block_hash='A' * 64)
        clone = BlockMetaDataRequest.from_bytes(req.serialize())

        self.assertEquals(clone, req)

    def test_create_with_bad_hash(self):
        bad_hash = 'lol this is fersure not a valid 64 hex char hash'
        self.assertRaises(Exception, BlockMetaDataRequest.create, bad_hash)


class TestBlockMetaDataReply(TestCase):

    def test_create_fails_with_invalid_blockmetas(self):
        """
        Tests that an assertion is raised if BlockMetaDataReply.create(...) is called with a list that contains a
        non BlockMetaData instance
        """
        # TODO implement
        pass

    def test_create_with_no_blocks(self):
        reply = BlockMetaDataReply.create(block_metas=None)

        self.assertFalse(reply.block_metas)

    def test_create_with_blocks(self):
        # TODO set block_metas to list of BlockMetaData instances
        block_metas = [b'1', b'2', b'3', b'4']  # in reality this should be a list of BlockMetaData instances
        reply = BlockMetaDataReply.create(block_metas=block_metas)

        for expected, actual in zip(reply.block_metas, block_metas):
            self.assertEquals(expected, actual)
