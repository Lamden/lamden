from cilantro.models import ModelBase
import hashlib
from cilantro import Constants
import json

class MerkleTree(ModelBase):
    name = "MERKLE_TREE"

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
        [h.update(o) for o in self.nodes]
        return h.digest()

    def deserialize_struct(cls, data: bytes):
        return json.loads(data.decode())

    def validate(self):
        assert 'vk' in self._data, "Vk field missing"
        assert 'signature' in self._data, "Signature field missing"

    def serialize_with_key(self, signing_key):
        verifying_key = Constants.Protocol.Wallets.signing_to_verifying(signing_key)
        sig = Constants.Protocol.Wallets.sign(signing_key, self.hash_of_nodes().encode())
        return json.dumps({'vk': verifying_key, 'signature': sig}).encode()

    @staticmethod
    def hash(o):
        h = hashlib.sha3_256()
        h.update(o)
        return h.digest()