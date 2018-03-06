from unittest import TestCase
from cilantro.models.merkle import MerkleTree

class TestMerkleTree(TestCase):
    def test_construction_1(self):
        should_be = [None, None, None, 1, 2, 3, 4]
        m = MerkleTree([1, 2, 3, 4])
        self.assertEqual(len(should_be), len(m.nodes))

    def test_construction_2(self):
        should_be = [None, None, 1, 2, 3]
        m = MerkleTree([1, 2, 3])
        self.assertEqual(len(should_be), len(m.nodes))

    def test_construction_3(self):
        should_be = [None, None, None, None, None, 1, 2, 3, 4, 5, 6]
        m = MerkleTree([1, 2, 3, 4, 5, 6])
        self.assertEqual(len(should_be), len(m.nodes))

    def test_make_merkle_works(self):
        # create a merkle tree that should be
        leaves = [1, 2, 3, 4]


        # hash leaves
        leaves = [MerkleTree.hash(bytes(l)) for l in leaves]
        m = MerkleTree(leaves)
        print(leaves)

        i = m.size - len(leaves)
        print(i)
        while i >= 1:
            true_i = i - 1
            m.nodes[true_i] = MerkleTree.hash(m.nodes[2*i-1] + m.nodes[2*i])
            i -= 1

        from pprint import pprint
        pprint(m.nodes, width=120)
