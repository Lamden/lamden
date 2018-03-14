from cilantro.models import ModelBase
import hashlib
import json
from cilantro import Constants


class MerkleSignature(ModelBase):
    """
    _data is a dict with keys: 'signature', 'timestamp', 'sender'
    """
    name = "MERKLE_SIGNATURE"

    SIG = 'signature'
    TS = 'timestamp'
    SENDER = 'sender'

    def validate(self):
        assert type(self._data) == dict, "_data is not a dictionary"
        assert self.SIG in self._data, "Signature field missing from _data: {}".format(self._data)
        assert self.TS in self._data, "Timestamp field missing from _data: {}".format(self._data)
        assert self.SENDER in self._data, "Sender field missing from _data: {}".format(self._data)

    def serialize(self):
        return json.dumps(self._data).encode()

    def verify(self, msg, verifying_key):
        # TODO validate verifying key and signature (hex, 64 char)
        return Constants.Protocol.Wallets.verify(verifying_key, msg, self.signature)

    @classmethod
    def from_fields(cls, sig_hex: str, timestamp: str, sender: str, validate=True):
        data = {cls.SIG: sig_hex, cls.TS: timestamp, cls.SENDER: sender}
        return cls.from_data(data, validate=validate)

    @classmethod
    def deserialize_data(cls, data: bytes):
        return json.loads(data.decode())

    @property
    def signature(self):
        return self._data[self.SIG]

    @property
    def timestamp(self):
        return self._data[self.TS]

    @property
    def sender(self):
        return self._data[self.SENDER]


class BlockContender(ModelBase):
    """
    _data is a dict with keys:
        'signature': [MerkleSignature1, MerkleSignature2, MerkleSignature3, ....]
            (all entries are MerkleSignature objects)
        'nodes': [root hash, root left hash, root right hash, root left left hash ... ]
            (all entries are hex strings)
    """
    name = "BLOCK_CONTENDER"

    SIGS = 'signature'
    NODES = 'nodes'

    def validate(self):
        pass

    def serialize(self):
        # loop through signatures list, serialize each
        # json dump entire _data
        pass

    @classmethod
    def deserialize_data(cls, data: bytes):
        # json loads entire data
        # deserialize each signature
        pass

    @property
    def signatures(self):
        return self._data[self.SIGS]

    @property
    def nodes(self):
        return self._data[self.NODES]


class MerkleTree:
    """
    TODO -- figure out what module this sort of "data creation" logic should live in
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