from unittest import TestCase
from cilantro.messages.consensus.merkle import MerkleTree


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
        test_merkle = [None,
                       None,
                       None,
                       MerkleTree.hash(bytes(1)),
                       MerkleTree.hash(bytes(2)),
                       MerkleTree.hash(bytes(3)),
                       MerkleTree.hash(bytes(4))]

        test_merkle[2] = MerkleTree.hash(test_merkle[-2] + test_merkle[-1])
        test_merkle[1] = MerkleTree.hash(test_merkle[3] + test_merkle[4])
        test_merkle[0] = MerkleTree.hash(test_merkle[1] + test_merkle[2])

        m = MerkleTree(leaves)

        self.assertEqual(test_merkle, m.nodes)

    def test_find_root(self):
        leaves = [1, 2, 3, 4]
        test_merkle = [None,
                       None,
                       None,
                       MerkleTree.hash(bytes(1)),
                       MerkleTree.hash(bytes(2)),
                       MerkleTree.hash(bytes(3)),
                       MerkleTree.hash(bytes(4))]

        test_merkle[2] = MerkleTree.hash(test_merkle[-2] + test_merkle[-1])
        test_merkle[1] = MerkleTree.hash(test_merkle[3] + test_merkle[4])
        test_merkle[0] = MerkleTree.hash(test_merkle[1] + test_merkle[2])

        m = MerkleTree(leaves)

        self.assertEqual(m.root(2), test_merkle[0])
        self.assertEqual(m.root(4), test_merkle[1])
        self.assertEqual(m.root(), test_merkle[0])

    def test_find_children(self):
        leaves = [1, 2, 3, 4]
        test_merkle = [None,
                       None,
                       None,
                       MerkleTree.hash(bytes(1)),
                       MerkleTree.hash(bytes(2)),
                       MerkleTree.hash(bytes(3)),
                       MerkleTree.hash(bytes(4))]

        test_merkle[2] = MerkleTree.hash(test_merkle[-2] + test_merkle[-1])
        test_merkle[1] = MerkleTree.hash(test_merkle[3] + test_merkle[4])
        test_merkle[0] = MerkleTree.hash(test_merkle[1] + test_merkle[2])

        m = MerkleTree(leaves)

        self.assertEqual(m.children(0), [test_merkle[1], test_merkle[2]])
        self.assertEqual(m.children(1), [test_merkle[3], test_merkle[4]])
        self.assertEqual(m.children(2), [test_merkle[5], test_merkle[6]])