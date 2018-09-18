from cilantro.messages.consensus.full_block_hash import FullBlockHash
from cilantro.utils import Hasher
from unittest import TestCase
import unittest

class TestBlockMetaDataRequest(TestCase):

    def test_create(self):
        b_hash = 'x' * 64 * 4
        fbh = FullBlockHash.create(b_hash)

        self.assertEqual(fbh.full_block_hash, Hasher.hash(b_hash))

    def test_serialize_deserialize(self):
        b_hash = 'x' * 64 * 4
        fbh = FullBlockHash.create(b_hash)
        clone = FullBlockHash.from_bytes(fbh.serialize())

        self.assertEqual(clone, fbh)

if __name__ == '__main__':
    unittest.main()
