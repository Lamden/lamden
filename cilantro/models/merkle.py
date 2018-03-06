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

    def get_root_for_index(self, i):
        pass

    def get_children_for_index(self, i):
        pass

    def get_root_for_hash(self, h):
        pass

    def get_children_for_hash(self, h):
        pass

    @staticmethod
    def hash(o):
        h = hashlib.sha3_256()
        h.update(o)
        return h.digest()
