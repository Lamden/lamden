import hashlib

class MerkleTree:
    """
    Data structure for computing a merkle tree
    """

    def __init__(self, leaves=None):
        self.raw_leaves = leaves

        # compute size of tree
        self.size = (len(leaves) * 2) - 1

        # prehash leaves
        self.leaves = [MerkleTree.hash(bytes(l)) for l in leaves]

        # create empty nodes until we hash it
        self.nodes = [None for _ in range(len(self.leaves) - 1)]
        self.nodes.extend(self.leaves)

        # hash the nodes
        for i in range(self.size - len(self.leaves), 0, -1):
            true_i = i - 1
            self.nodes[true_i] = \
                MerkleTree.hash(self.nodes[2 * i - 1] +
                                self.nodes[2 * i])

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
        h = hashlib.sha3_256()
        # is this any better or worse than passing around the merkle root?
        [h.update(o) for o in self.nodes]
        return h.digest()

    @staticmethod
    def hash(o):
        h = hashlib.sha3_256()
        h.update(o)
        return h.digest()
