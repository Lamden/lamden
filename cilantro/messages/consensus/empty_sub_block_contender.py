from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property, set_lazy_property, is_valid_hex
from cilantro.messages.consensus.merkle_signature import MerkleSignature
import pickle

import capnp
import subblock_capnp

class EmptySubBlockContender(MessageBase):
    # TODO switch underlying data struct for this guy to Capnp (or at least JSON)
    """
    EmptySubBlockContender is the message object that is published to master nodes
    when delegate doesn't have transactions at that time.
    """

    def validate(self):
        # Validate field types and existence
        assert self._data.input_hash, "input hash field missing from data {}".format(self._data)
        # leaves can be empty list from some delegates that only intend to vote (not propose it)
        assert self._data.signature, "Signature field missing from data {}".format(self._data)

        assert is_valid_hex(self.input_hash, length=64), "Invalid input sub-block hash {} .. " \
                                                         "expected 64 char hex string".format(self.input_hash)

        # Attempt to deserialize signatures by reading property (will raise exception if can't)
        # self.signature.verify(self.input_hash)   # do we need this ??

    @classmethod
    def create(cls, input_hash: str, sb_idx: int, signature: MerkleSignature):
        """
        :param input_hash: The hash of input bag containing raw txns in order
        :param sb_idx: Index of this sub-block 
        :param signature: MerkleSignature of the delegate proposing this sub-block
        :return: A SubBlockContender object
        """
        assert isinstance(signature, MerkleSignature), "signature must be of MerkleSignature"

        struct = subblock_capnp.EmptySubBlockContender.new_message()
        struct.input_hash = input_hash
        struct.sb_index = sb_idx
        struct.signature = signature.serialize()

        return cls.from_data(struct)


    @classmethod
    def _chunks(cls, l, n=64):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return subblock_capnp.SubBlockContender.from_bytes_packed(data)

    @property
    def input_hash(self) -> str:
        return self._data.input_hash.decode()

    @lazy_property
    def signature(self) -> MerkleSignature:
        """
        MerkleSignature of the delegate that proposed this sub-block
        """
        # Deserialize signatures
        return MerkleSignature.from_bytes(self._data.signature)

    def __eq__(self, other):
        assert isinstance(other, EmptySubBlockContender), "Attempted to compare a EmptySubBlockContender with a non-EmptySubBlockContender"
        return self.input_hash == other.input_hash and \
            self.sb_index == other.sb_index
