from cilantro.messages import MessageBase, MerkleSignature
import pickle

"""
TODO -- docstring and class description 
TODO -- switch this class to use capnp 
"""

class BlockContender(MessageBase):
    """
    _data is a dict with keys:
        'signature': [MerkleSignature1, MerkleSignature2, MerkleSignature3, ....]
            (all entries are MerkleSignature objects)
        'nodes': is a list of hashes of leaves
    """
    SIGS = 'signature'
    NODES = 'nodes'

    def validate(self):
        assert type(self._data) == dict, "BlockContender's _data must be a dict"
        assert BlockContender.SIGS in self._data, "signature field missing from data {}".format(self._data)
        assert BlockContender.NODES in self._data, "nodes field missing from data {}".format(self._data)

    def serialize(self):
        for i in range(len(self._data[self.SIGS])):
            self._data[self.SIGS][i] = self._data[self.SIGS][i].serialize()
        return pickle.dumps(self._data)

    @classmethod
    def create(cls, signatures: list, nodes: list):
        data = {cls.SIGS: signatures, cls.NODES: nodes}
        return cls.from_data(data)

    @classmethod
    def _deserialize_data(cls, data: bytes):
        data = pickle.loads(data)
        for i in range(len(data[cls.SIGS])):
            data[cls.SIGS][i] = MerkleSignature.from_bytes(data[cls.SIGS][i])
        return data

    @property
    def signatures(self):
        return self._data[self.SIGS]

    @property
    def nodes(self):
        return self._data[self.NODES]
