from cilantro.messages import MessageBase
from cilantro.utils import lazy_property, set_lazy_property
from cilantro.messages.consensus.merkle_signature import MerkleSignature
import pickle
from typing import List


"""
A BlockContender is produced by a delegate once he/she has collected sufficient signatures from other delegates during
consensus state. It is the sent to a Masternode, who validates the contender, requests the transactional data, and if
all succeeds, publishes a new block
"""


# TODO switch underlying data struct for this guy to Capnp
class BlockContender(MessageBase):
    """
    _data is a dict with keys:
        'signatures': [MerkleSignature1, MerkleSignature2, MerkleSignature3, ....]
            ...all entries are serialized MerkleSignature objects (of type bytes)
        'nodes': is a list of hashes of leaves (list of bytes)
    """
    SIGS = 'signatures'
    NODES = 'nodes'

    def validate(self):
        assert type(self._data) == dict, "BlockContender's _data must be a dict"
        assert BlockContender.SIGS in self._data, "signature field missing from data {}".format(self._data)
        assert BlockContender.NODES in self._data, "nodes field missing from data {}".format(self._data)

        # Attempt to deserialize signatures by reading property (will raise expection if can't)
        self.signatures

    def serialize(self):
        return pickle.dumps(self._data)

    @classmethod
    def create(cls, signatures: list, nodes: list):
        # Serialize list of signatures
        sigs_binary = []

        for sig in signatures:
            assert isinstance(sig, MerkleSignature), "signatures must be a list of MerkleSignatures"
            sigs_binary.append(sig.serialize())

        data = {cls.SIGS: sigs_binary, cls.NODES: nodes}
        obj = cls.from_data(data)

        set_lazy_property(obj, 'signatures', signatures)

        return obj

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return pickle.loads(data)

    @lazy_property
    def signatures(self) -> List[MerkleSignature]:
        """
        A list of MerkleSignatures, signed by delegates who were in consensus with this Contender's sender
        """
        # Deserialize signatures
        sigs = []
        for i in range(len(self._data[BlockContender.SIGS])):
            sigs.append(MerkleSignature.from_bytes(self._data[BlockContender.SIGS][i]))
        return sigs

    @property
    def nodes(self) -> List[str]:
        """
        The Merkle Tree associated with the block (a binary tree stored implicitly as a list). Each element is hex string
        representing a node's hash.
        """
        return self._data[self.NODES]
