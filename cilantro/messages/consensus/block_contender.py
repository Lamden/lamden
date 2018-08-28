from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property, set_lazy_property, is_valid_hex
from cilantro.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig
from cilantro.protocol.structures import MerkleTree
import pickle
from typing import List


class BlockContender(MessageBase):
    # TODO switch underlying data struct for this guy to Capnp (or at least JSON)
    """
    BlockContender is the message object that is passed to masternode after consensus has been reached and a valid block
    has been produced. It contains a list of MerkleSignatures, as well as a list of Merkle leaves (the hashes of the
    transactions in the block)
    """

    SIGS = 'signatures'
    LEAVES = 'leaves'
    PREV_BLOCK = 'prev_block_hash'

    def validate(self):
        # Validate field types and existence
        assert type(self._data) == dict, "BlockContender's _data must be a dict"
        assert BlockContender.SIGS in self._data, "signature field missing from data {}".format(self._data)
        assert BlockContender.LEAVES in self._data, "leaves field missing from data {}".format(self._data)

        assert is_valid_hex(self.prev_block_hash, length=64), "Invalid previous block hash {} .. " \
                                                              "expected 64 char hex string".format(self.prev_block_hash)

        # Ensure merkle leaves are valid hex
        for leaf in self.merkle_leaves:
            assert is_valid_hex(leaf, length=64), "Invalid Merkle leaf {} ... expected 64 char hex string".format(leaf)

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
    def create(cls, signatures: List[MerkleSignature], merkle_leaves: List[str], prev_block_hash: str):
        """
        Creates a new block contender. Created by delegates to propose a block to Masternodes.
        :param signatures: A list of MerkleSignature objects
        :param merkle_leaves: A list merkle leaves contained within this proposed block. Each leaf is a byte string
        :param prev_block_hash: The hash of the previous (parent) block upon which this proposed block would build upon
        :return: A BlockContender object
        """
        # Serialize list of signatures
        sigs_binary = []

        for sig in signatures:
            assert isinstance(sig, MerkleSignature), "signatures must be a list of MerkleSignatures"
            sigs_binary.append(sig.serialize())

        data = {cls.SIGS: sigs_binary, cls.LEAVES: merkle_leaves, cls.PREV_BLOCK: prev_block_hash}
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
    def prev_block_hash(self) -> str:
        return self._data[self.PREV_BLOCK]

    @property
    def merkle_leaves(self) -> List[str]:
        """
        The Merkle Tree leaves associated with the block (a binary tree stored implicitly as a list).
        Each element is hex string representing a node's hash.
        """
        return self._data[self.LEAVES]

    def __eq__(self, other):
        assert isinstance(other, BlockContender), "Attempted to compare a BlockContender with a non-BlockContender"

        # Compare signature objects
        if len(self.signatures) != len(other.signatures):
            return False
        for sig1, sig2 in zip(self.signatures, other.signatures):
            if sig1 != sig2:
                return False

        # Compare leaves
        if len(self.merkle_leaves) != len(other.merkle_leaves):
            return False
        for leaf1, leaf2, in zip(self.merkle_leaves, other.merkle_leaves):
            if leaf1 != leaf2:
                return False

        return True


def build_test_contender(tree: MerkleTree=None, prev_block_hash=''):
    """
    Method to build a 'test' block contender. Used exclusively in unit tests.
    """
    from cilantro.storage.blocks import BlockStorageDriver
    from cilantro.constants.nodes import BLOCK_SIZE

    if not tree:
        nodes = [str(i).encode() for i in range(BLOCK_SIZE)]
        tree = MerkleTree(leaves=nodes)

    if not prev_block_hash:
        prev_block_hash = BlockStorageDriver.get_latest_block_hash()

    sigs = [build_test_merkle_sig(msg=tree.root) for _ in range(8)]
    return BlockContender.create(signatures=sigs, merkle_leaves=tree.leaves_as_hex, prev_block_hash=prev_block_hash)
