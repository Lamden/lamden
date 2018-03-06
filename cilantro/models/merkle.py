from cilantro.models import ModelBase
import hashlib


class MerkleTree(ModelBase):
    def __init__(self, leaves=None):
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

    @staticmethod
    def hash(o):
        h = hashlib.sha3_256()
        h.update(o)
        return h.digest()
