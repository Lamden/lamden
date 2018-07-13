from cilantro.messages import MessageBase
from cilantro.utils import lazy_property, set_lazy_property
from cilantro.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig
from cilantro.protocol.structures import MerkleTree
import pickle
from typing import List


class BlockContender(MessageBase):
    # TODO switch underlying data struct for this guy to Capnp
    """
    BlockContender is the message object that is passed to masternode after consensus has been reached and a valid block
    has been produced. It contains a list of MerkleSignatures, as well as a list of Merkle leaves (the hashes of the
    transactions in the block)
    """

    SIGS = 'signatures'
    NODES = 'nodes'

    def validate(self):
        # Validate field types and existence
        assert type(self._data) == dict, "BlockContender's _data must be a dict"
        assert BlockContender.SIGS in self._data, "signature field missing from data {}".format(self._data)
        assert BlockContender.NODES in self._data, "nodes field missing from data {}".format(self._data)

        # Attempt to deserialize signatures by reading property (will raise exception if can't)
        self.signatures

    def validate_signatures(self):
        """
        Validates the signatures in the block contender. Returns true if all signatures are valid, and false otherwise
        :return: True if the signatures are valid; False otherwise
        """
        tree = MerkleTree.from_hex_leaves(self.merkle_leaves)

        for sig in self.signatures:
            if not sig.verify(tree.root):
                return False
        return True

    def serialize(self):
        return pickle.dumps(self._data)

    @classmethod
    def create(cls, signatures: List[MerkleSignature], merkle_leaves: List[str]):
        """
        Creates a new block contender. Created by delegates to propose a block to Masternodes.
        :param signatures: A list of MerkleSignature objects
        :param merkle_leaves: A list merkle leaves contained within this proposed block. Each leaf is a byte string
        :return: A BlockContender object
        """
        # Serialize list of signatures
        sigs_binary = []

        for sig in signatures:
            assert isinstance(sig, MerkleSignature), "signatures must be a list of MerkleSignatures"
            sigs_binary.append(sig.serialize())

        data = {cls.SIGS: sigs_binary, cls.NODES: merkle_leaves}
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
        return [MerkleSignature.from_bytes(self._data[BlockContender.SIGS][i])
                for i in range(len(self._data[BlockContender.SIGS]))]

    @property
    def merkle_leaves(self) -> List[str]:
        """
        The Merkle Tree leaves associated with the block (a binary tree stored implicitly as a list).
        Each element is hex string representing a node's hash.
        """
        return self._data[self.NODES]


def build_test_contender(tree: MerkleTree=None):
    """
    Method to build a 'test' block contender. Used exclusively in unit tests.
    """
    if not tree:
        nodes = [1, 2, 3, 4]
        tree = MerkleTree(leaves=nodes)

    sigs = [build_test_merkle_sig(msg=tree.root) for _ in range(8)]
    return BlockContender.create(signatures=sigs, merkle_leaves=tree.leaves_as_hex)
