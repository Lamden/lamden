from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property, set_lazy_property, is_valid_hex
from cilantro.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig
from cilantro.protocol.structures import MerkleTree
import pickle
from typing import List


class SubBlockContender(MessageBase):
    # TODO switch underlying data struct for this guy to Capnp (or at least JSON)
    """
    SubBlockContender is the message object that is published to master nodes (and other delegates - may be this is not needed)
    when a valid sub-block is produced at a delegate.
    It contains a list of Merkle leaves (the hashes of the transactions in the block) along with input hash, result hash,
    signagure of the delegate and some raw transactions
    """

    RESULT_HASH = 'result_hash'     # root hash
    INPUT_HASH = 'input_hash'       # hash of input txn bag ??
    LEAVES = 'leaves'               # set of txn_hashes ?  presence of this could be block contender or vote only
    SIG = 'signature'               # set of signatures 
    TXNS = 'raw_txns'               # partial set of raw txns
 
    # NODES = 'nodes'      # do we need intermediate nodes ?? if so, it could double the data?
    

    def validate(self):
        # Validate field types and existence
        assert type(self._data) == dict, "SubBlockContender's _data must be a dict"
        assert SubBlockContender.RESULT_HASH in self._data, "result hash field missing from data {}".format(self._data)
        assert SubBlockContender.INPUT_HASH in self._data, "input hash field missing from data {}".format(self._data)
        # leaves can be empty list from some delegates that only intend to vote (not propose it)
        assert SubBlockContender.LEAVES in self._data, "leaves field missing from data {}".format(self._data)
        assert SubBlockContender.SIG in self._data, "Signature field missing from data {}".format(self._data)
        # assert SubBlockContender.NODES in self._data, "nodes field missing from data {}".format(self._data)
        assert SubBlockContender.TXNS in self._data, "Raw transactions field missing from data {}".format(self._data)

        assert is_valid_hex(self.result_hash, length=64), "Invalid sub-block result hash {} .. " \
                                                          "expected 64 char hex string".format(self.prev_block_hash)
        assert is_valid_hex(self.input_hash, length=64), "Invalid input sub-block hash {} .. " \
                                                         "expected 64 char hex string".format(self.prev_block_hash)

        # Ensure merkle leaves are valid hex - this may not be present in all cases
        for leaf in self.merkle_leaves:
            assert is_valid_hex(leaf, length=64), "Invalid Merkle leaf {} ... expected 64 char hex string".format(leaf)

        # Attempt to deserialize signatures by reading property (will raise exception if can't)
        self.signature

    def validate_signature(self):
        """
        Validates the signature in the block contender.
        :return: True if the signature is valid; False otherwise
        """
        return self.signature.verify(self.result_hash)

    def serialize(self):
        return pickle.dumps(self._data)

    @classmethod
    def create(cls, result_hash: str, input_hash: str, mrkel_leaves: List[str],
               signature: MerkleSignature, raw_txns: List[bytes]):
        # raw_txns -> list of (hash: raw_txns) pairs
        """
        Delegages create a new sub-block contender and propose to master nodes
        :param result_hash: The hash of the root of this sub-block
        :param input_hash: The hash of input bag containing raw txns in order
        :param merkle_leaves: A list merkle leaves contained within this proposed block. Each leaf is a byte string
        :param signature: MerkleSignature of the delegate proposing this sub-block
        :param raw_txns: Partial set of raw transactions with the result state included.
        :return: A SubBlockContender object
        """
        # Serialize list of signatures
        sigs_binary = []

        for sig in signatures:
            sigs_binary.append(sig.serialize())

        assert isinstance(signature, MerkleSignature), "signature must be of MerkleSignature"
        data = {cls.SIGS: sigs_binary, cls.LEAVES: merkle_leaves, cls.PREV_BLOCK: prev_block_hash}
        obj = cls.from_data(data)

        set_lazy_property(obj, 'signature', signature)

        return obj

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return pickle.loads(data)

    @lazy_property
    def signature(self) -> MerkleSignature:
        """
        MerkleSignature of the delegate that proposed this sub-block
        """
        # Deserialize signatures
        return MerkleSignature.from_bytes(self._data[SubBlockContender.SIG])

    @property
    def input_hash(self) -> str:
        return self._data[self.INPUT_HASH]

    @property
    def result_hash(self) -> str:
        return self._data[self.RESULT_HASH]

    @property
    def merkle_leaves(self) -> List[str]:
        """
        The Merkle Tree leaves associated with the block (a binary tree stored implicitly as a list).
        Each element is hex string representing a node's hash.
        """
        return self._data[self.LEAVES]

    def __eq__(self, other):
        assert isinstance(other, SubBlockContender), "Attempted to compare a BlockContender with a non-BlockContender"

        # Compare sub-block hash
        if self.input_hash != other.input_hash:
            return False
        # Compare result (sub-root) hash
        return self.result_hash == other.result_hash
