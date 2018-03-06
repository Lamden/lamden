from unittest import TestCase
from cilantro.models.merkle import MerkleTree

class TestMerkleTree(TestCase):
    def test_construction_1(self):
        should_be = [None, None, None, 1, 2, 3, 4]
        m = MerkleTree([1, 2, 3, 4])
        self.assertEqual(should_be, m.nodes)

    def test_construction_2(self):
        should_be = [None, None, 1, 2, 3]
        m = MerkleTree([1, 2, 3])
        self.assertEqual(should_be, m.nodes)

    def test_construction_3(self):
        should_be = [None, None, None, None, None, 1, 2, 3, 4, 5, 6]
        m = MerkleTree([1, 2, 3, 4, 5, 6])
        self.assertEqual(should_be, m.nodes)