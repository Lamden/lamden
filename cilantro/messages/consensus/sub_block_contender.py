from cilantro.messages.base.base import MessageBase
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.utils import lazy_property, set_lazy_property, is_valid_hex
from cilantro.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig
from cilantro.protocol.structures import MerkleTree
import pickle
from typing import List

import capnp
import subblock_capnp

class SubBlockContender(MessageBase):
    # TODO switch underlying data struct for this guy to Capnp (or at least JSON)
    """
    SubBlockContender is the message object that is published to master nodes (and other delegates - may be this is not needed)
    when a valid sub-block is produced at a delegate.
    It contains a list of Merkle leaves (the hashes of the transactions in the block) along with input hash, result hash,
    signagure of the delegate and some raw transactions
    """

    def validate(self):
        # Validate field types and existence
        assert self._data.resultHash, "result hash field missing from data {}".format(self._data)
        assert self._data.inputHash, "input hash field missing from data {}".format(self._data)
        # leaves can be empty list from some delegates that only intend to vote (not propose it)
        assert self._data.merkleLeaves, "leaves field missing from data {}".format(self._data)
        assert self._data.signature, "Signature field missing from data {}".format(self._data)
        assert self._data.transactions, "Raw transactions field missing from data {}".format(self._data)

        assert is_valid_hex(self.result_hash, length=64), "Invalid sub-block result hash {} .. " \
                                                          "expected 64 char hex string".format(self.result_hash)
        assert is_valid_hex(self.input_hash, length=64), "Invalid input sub-block hash {} .. " \
                                                         "expected 64 char hex string".format(self.input_hash)

        # Ensure merkle leaves are valid hex - this may not be present in all cases
        for leaf in self.merkle_leaves:
            assert is_valid_hex(leaf, length=64), "Invalid Merkle leaf {} ... expected 64 char hex string".format(leaf)

        assert len(list(set(self._data.transactions))) == len(self._data.merkleLeaves), \
            'Delegate did not include all transactions!'

        # Attempt to deserialize signatures by reading property (will raise exception if can't)
        self.signature.verify(self.result_hash)

    @classmethod
    def create(cls, result_hash: str, input_hash: str, merkle_leaves: List[bytes],
               sb_index: int, signature: MerkleSignature, raw_txs: List[bytes]):
        """
        Delegages create a new sub-block contender and propose to master nodes
        :param result_hash: The hash of the root of this sub-block
        :param input_hash: The hash of input bag containing raw txns in order
        :param merkle_leaves: A list merkle leaves contained within this proposed block. Each leaf is a byte string
        :param signature: MerkleSignature of the delegate proposing this sub-block
        :param raw_txs: Partial set of raw transactions with the result state included.
        :return: A SubBlockContender object
        """
        assert isinstance(signature, MerkleSignature), "signature must be of MerkleSignature"

        struct = subblock_capnp.SubBlockContender.new_message()
        struct.init('merkleLeaves', len(merkle_leaves))
        struct.init('transactions', len(raw_txs))
        struct.resultHash = result_hash
        struct.inputHash = input_hash
        struct.sb_index = sb_index
        struct.merkleLeaves = merkle_leaves
        struct.signature = signature.serialize()
        struct.transactions = raw_txs

        return cls.from_data(struct)

    @classmethod
    def _chunks(cls, l, n=64):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return subblock_capnp.SubBlockContender.from_bytes_packed(data)

    @property
    def result_hash(self) -> str:
        return self._data.resultHash.hex()

    @property
    def input_hash(self) -> str:
        return self._data.inputHash.decode()

    @lazy_property
    def signature(self) -> MerkleSignature:
        """
        MerkleSignature of the delegate that proposed this sub-block
        """
        # Deserialize signatures
        return MerkleSignature.from_bytes(self._data.signature)

    @property
    def merkle_leaves(self) -> List[str]:
        """
        The Merkle Tree leaves associated with the block (a binary tree stored implicitly as a list).
        Each element is hex string representing a node's hash.
        """
        return [leaf.hex() for leaf in self._data.merkleLeaves]

    @property
    def transactions(self) -> List[ContractTransaction]:
        """
        The Merkle Tree leaves associated with the block (a binary tree stored implicitly as a list).
        Each element is hex string representing a node's hash.
        """
        return [ContractTransaction.from_bytes(tx) for tx in self._data.transactions]

    def __eq__(self, other):
        assert isinstance(other, SubBlockContender), "Attempted to compare a BlockContender with a non-BlockContender"
        return self.input_hash == other.input_hash and \
            self.result_hash == other.result_hash
