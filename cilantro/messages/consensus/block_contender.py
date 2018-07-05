from cilantro.messages import MessageBase
from cilantro.utils import lazy_property, set_lazy_property
from cilantro.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig
from cilantro.protocol.structures import MerkleTree
import pickle
from typing import List


class BlockContender(MessageBase):
    # TODO switch underlying data struct for this guy to Capnp
    """
    BlockContender is the message object that is passed between delegates during consensus state. It consists of the merkle
    signature roots of all the transactions in the block by the block validators.

    BlockContender is the message object that is passed to masternode after consensus has been reached and a valid block
    has been produced.

    _data is a dict with keys:
        'signatures': [MerkleSignature1, MerkleSignature2, MerkleSignature3, ....]
            ...all entries are serialized MerkleSignature objects (of type bytes)
        'nodes': is a list of hashes of leaves (list of bytes)
    """

    SIGS = 'signatures'
    NODES = 'nodes'

    def validate(self):
        # Validate field types and existence
        assert type(self._data) == dict, "BlockContender's _data must be a dict"
        assert BlockContender.SIGS in self._data, "signature field missing from data {}".format(self._data)
        assert BlockContender.NODES in self._data, "nodes field missing from data {}".format(self._data)

        # Attempt to deserialize signatures by reading property (will raise expection if can't)
        self.signatures

    def _validate_signatures(self):
        """
        Validates the signatures in the block contender. Raises an error if a signature cannot be validated
        """
        hash_of_nodes = MerkleTree.hash_nodes(self.nodes)

        for sig in self.signatures:
            assert isinstance(sig, MerkleSignature), "signatures must be a list of MerkleSignatures"
            assert sig.validate()

    def serialize(self):
        return pickle.dumps(self._data)

    @classmethod
    def create(cls, signatures: list, nodes: list):
        """
        Creates a new block contender. Created by delegates to propose a block to Masternodes.
        :param signatures: A list of MerkleSignature objects
        :param nodes: A list of hashes of leaves (a list of byte objects)
        :return:
        """
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


def build_test_contender():
    """
    Method to build a 'test' block contender. Used exclusively in unit tests.
    """
    sigs = [build_test_merkle_sig() for _ in range(8)]
    nodes = [1, 2, 3, 4]

    return BlockContender.create(signatures=sigs, nodes=nodes)
