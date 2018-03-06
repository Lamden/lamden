from cilantro.models import ModelBase
import hashlib


class MerkleTree(ModelBase):
    def __init__(self, leaves=None):
        self.size = (len(leaves) * 2) - 1

        self.nodes = [None for _ in range(len(leaves) - 1)]
        self.nodes.extend(leaves)

    def get_root_for_index(self, i):
        pass

    def get_children_for_index(self, i):
        pass

    def get_root_for_hash(self, h):
        pass

    def get_children_for_hash(self, h):
        pass

    @staticmethod
    def hash(o: bytes):
        h = hashlib.sha3_256()
        h.update(o)
        return h.digest()

# create a merkle tree that should be
l = [1, 2, 3, 4]
mt = [None, None, None, 1, 2, 3, 4]
mt[1] = MerkleTree.hash(MerkleTree.hash(bytes(1)) + MerkleTree.hash(bytes(2)))
mt[2] = MerkleTree.hash(MerkleTree.hash(bytes(3)) + MerkleTree.hash(bytes(4)))
mt[0] = MerkleTree.hash(MerkleTree.hash(bytes(mt[1])) + MerkleTree.hash(bytes(mt[2])))
from pprint import pprint
pprint(mt)