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
