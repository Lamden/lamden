from cilantro.utils import Hasher


class MerkleTree:
    """
    Data structure for computing a merkle tree
    """

    def __init__(self, leaves=None):
        self.raw_leaves = leaves
        self.nodes = MerkleTree.merklize(leaves)

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
        return Hasher.hash_iterable(self.nodes, algorithm=Hasher.Alg.SHA3_256, return_bytes=True)

    @staticmethod
    def verify_tree(tree_nodes: list, tree_hash: bytes):
        nodes = MerkleTree.merklize(tree_nodes, hash_leaves=False)
        h = Hasher.hash_iterable(nodes, algorithm=Hasher.Alg.SHA3_256, return_bytes=True)
        return h == tree_hash

    @staticmethod
    def merklize(leaves: list, hash_leaves=True) -> list:
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
