from cilantro.utils import Hasher


class MerkleTree:
    """
    Data structure for computing a merkle tree
    """

    def __init__(self, leaves=None):
        self.raw_leaves = leaves
        self.nodes = MerkleTree.merklize(leaves)
        self.leaves = self.nodes[-len(leaves):]

    def root(self, i=0):
        if i == 0:
            return self.nodes[0]
        return self.nodes[((i + 1) // 2) - 1]

    def children(self, i):
        return [
            self.nodes[((i + 1) * 2) - 1],
            self.nodes[(((i + 1) * 2) + 1) - 1]
        ]

    def data_for_hash(self, h):
        # gets data back for a given hash for propagating to masternode
        searchable_hashes = self.nodes[len(self.leaves) - 1:]
        if h in searchable_hashes:
            return self.raw_leaves[searchable_hashes.index(h)]
        return None

    def hash_of_nodes(self):
        return MerkleTree.hash_nodes(self.nodes)

    @staticmethod
    def verify_tree(nodes: list, tree_hash: bytes):
        """
        Attempts to verify merkle tree represented implicitly by the list 'nodes'. The tree is valid if it maintains
        the invariant that the value of each non-leaf node is the hash of its left child's value concatenated with
        its right child's value.
        :param nodes: The nodes in the tree, represented implicitly as a list
        :param tree_hash: The expected hash of the merkle tree formed from nodes (the 'hash of a merkle tree' is the
        value returned by the .hash_of_nodes method on this class)
        :return: True if the tree is valid; False otherwise
        """
        nodes = MerkleTree.merklize(nodes, hash_leaves=False)
        h = Hasher.hash_iterable(nodes, algorithm=Hasher.Alg.SHA3_256, return_bytes=True)
        return h == tree_hash

    @staticmethod
    def merklize(leaves: list, hash_leaves=True) -> list:
        """
        Builds a merkle tree from leaves and returns the tree as a list (representing an implicitly stored binary tree)
        :param leaves: The leaves to form a merkle tree from.
        :param hash_leaves: True if the leaves should be hashed before building the tree.
        :return: A list, which serves as an implicit representation of the merkle tree
        """
        if hash_leaves:
            leaves = [MerkleTree.hash(bytes(l)) for l in leaves]

        nodes = [None for _ in range(len(leaves) - 1)]
        nodes.extend(leaves)

        for i in range((len(leaves) * 2) - 1 - len(leaves), 0, -1):
            true_i = i - 1
            nodes[true_i] = \
                MerkleTree.hash(nodes[2 * i - 1] +
                                nodes[2 * i])

        return nodes

    @staticmethod
    def hash(o):
        return Hasher.hash(o, algorithm=Hasher.Alg.SHA3_256, return_bytes=True)

    @staticmethod
    def hash_nodes(nodes: list):
        return Hasher.hash_iterable(nodes, algorithm=Hasher.Alg.SHA3_256, return_bytes=True)
