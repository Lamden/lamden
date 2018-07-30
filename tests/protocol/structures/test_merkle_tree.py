from unittest import TestCase
from cilantro.utils import Hasher
from cilantro.protocol.structures import MerkleTree
import secrets


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
        leaves = [1, 2, 3, 4]
        test_merkle = [None,
                       None,
                       None,
                       MerkleTree.hash(1),
                       MerkleTree.hash(2),
                       MerkleTree.hash(3),
                       MerkleTree.hash(4)]

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
                       MerkleTree.hash(1),
                       MerkleTree.hash(2),
                       MerkleTree.hash(3),
                       MerkleTree.hash(4)]

        test_merkle[2] = MerkleTree.hash(test_merkle[-2] + test_merkle[-1])
        test_merkle[1] = MerkleTree.hash(test_merkle[3] + test_merkle[4])
        test_merkle[0] = MerkleTree.hash(test_merkle[1] + test_merkle[2])

        m = MerkleTree(leaves)

        self.assertEqual(m.parent(2), test_merkle[0])
        self.assertEqual(m.parent(4), test_merkle[1])
        self.assertEqual(m.parent(), test_merkle[0])
        self.assertEqual(m.root, test_merkle[0])

    def test_find_children(self):
        leaves = [1, 2, 3, 4]
        test_merkle = [None,
                       None,
                       None,
                       MerkleTree.hash(1),
                       MerkleTree.hash(2),
                       MerkleTree.hash(3),
                       MerkleTree.hash(4)]

        test_merkle[2] = MerkleTree.hash(test_merkle[-2] + test_merkle[-1])
        test_merkle[1] = MerkleTree.hash(test_merkle[3] + test_merkle[4])
        test_merkle[0] = MerkleTree.hash(test_merkle[1] + test_merkle[2])

        m = MerkleTree(leaves)

        self.assertEqual(m.children(0), [test_merkle[1], test_merkle[2]])
        self.assertEqual(m.children(1), [test_merkle[3], test_merkle[4]])
        self.assertEqual(m.children(2), [test_merkle[5], test_merkle[6]])

    def test_verify_tree(self):
        raw_leaves = [secrets.token_bytes(16) for _ in range(16)]

        m = MerkleTree(raw_leaves)

        self.assertTrue(MerkleTree.verify_tree(m.leaves, m.root))

    def test_verify_tree_from_hex_str(self):
        raw_leaves = [secrets.token_bytes(16) for _ in range(16)]

        m = MerkleTree(raw_leaves)

        self.assertTrue(MerkleTree.verify_tree_from_hex_str(m.leaves_as_concat_hex_str, m.root_as_hex))

    def test_verify_tree_from_hex_str_invalid(self):
        raw_leaves = [secrets.token_bytes(16) for _ in range(16)]
        random_hash = MerkleTree.hash(secrets.token_bytes(16))

        m = MerkleTree(raw_leaves)

        self.assertFalse(MerkleTree.verify_tree_from_hex_str(m.leaves_as_concat_hex_str, random_hash))

    def test_verify_tree_invalid(self):
        raw_leaves = [secrets.token_bytes(16) for _ in range(16)]

        m = MerkleTree(raw_leaves)

        # Set the last leaf to a random value obviously different then whatever was used to build the tree
        # this should cause validation to fail
        bad_leaves = m.leaves
        bad_leaves[-1] = secrets.token_bytes(16)

        self.assertFalse(MerkleTree.verify_tree(bad_leaves, m.root))

    def test_leaves_as_hex(self):
        leaves = [1, 2, 3, 4]
        hashed_leaves = [MerkleTree.hash(leaf).hex() for leaf in leaves]

        m = MerkleTree(leaves)

        for actual, expected in zip(m.leaves_as_hex, hashed_leaves):
            self.assertEqual(actual, expected)

    def test_root_as_hex(self):
        leaves = [1, 2, 3, 4]
        test_merkle = [None,
                       None,
                       None,
                       MerkleTree.hash(1),
                       MerkleTree.hash(2),
                       MerkleTree.hash(3),
                       MerkleTree.hash(4)]

        test_merkle[2] = MerkleTree.hash(test_merkle[-2] + test_merkle[-1])
        test_merkle[1] = MerkleTree.hash(test_merkle[3] + test_merkle[4])
        test_merkle[0] = MerkleTree.hash(test_merkle[1] + test_merkle[2])

        m = MerkleTree(leaves)

        self.assertEqual(m.root, test_merkle[0])
        self.assertEqual(m.root_as_hex, test_merkle[0].hex())

    def test_hash_leaves_false(self):
        leaves = [1, 2, 3, 4]
        prehashed_leaves = list(map(MerkleTree.hash, leaves))

        merk_from_leaves = MerkleTree(leaves=leaves)
        merk_from_hashes = MerkleTree(leaves=prehashed_leaves, hash_leaves=False)

        for node1, node2 in zip(merk_from_hashes.nodes, merk_from_leaves.nodes):
            self.assertEqual(node1, node2)

    def test_leaves_as_hex_str(self):
        leaves = [1, 2, 3, 4]
        hashed_leaves = [MerkleTree.hash(leaf).hex() for leaf in leaves]
        hex_leaves = ''.join(hashed_leaves)

        m = MerkleTree(leaves)

        self.assertEqual(hex_leaves, m.leaves_as_concat_hex_str)

    def test_from_leaves_hex_str(self):
        leaves = [1, 2, 3, 4]

        m_from_init = MerkleTree(leaves)
        m_from_hex_str = MerkleTree.from_leaves_hex_str(m_from_init.leaves_as_concat_hex_str)

        self.assertEqual(m_from_hex_str.root, m_from_init.root)

    def test_data_for_hash(self):
        leaves = [b'1', b'2', b'3']
        hashed_leaves = list(map(Hasher.hash, leaves))

        m = MerkleTree.from_raw_transactions(leaves)

        for i in range(len(leaves)):
            self.assertEquals(m.data_for_hash(hashed_leaves[i]), leaves[i])

    def test_data_for_hash_doesnt_exist(self):
        leaves = [b'1', b'2', b'3']
        hashed_leaves = list(map(Hasher.hash, leaves))

        m = MerkleTree.from_raw_transactions(leaves)

        self.assertRaises(AssertionError, m.data_for_hash, '0' * 64)

    # TODO test from raw leaves

    # TODO test from hex leaves

    # TODO test from raw transactions
