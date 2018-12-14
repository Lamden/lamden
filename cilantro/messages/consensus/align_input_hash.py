from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property, set_lazy_property, is_valid_hex

from typing import List

import capnp
import subblock_capnp


class AlignInputHash(MessageBase):
    # TODO switch underlying data struct for this guy to Capnp (or at least JSON)
    """
    AlignInputHash is the message object that is published to sub-block builders
    when the input hashes of new block notification doesn't match the input hashes of sub-block-contenders sent
    This message will help sub-block builders align their input bags
    It just contains a input hash
    """

    def validate(self):
        assert self._data.inputHash, "input hash field missing from data {}".format(self._data)
        assert is_valid_hex(self.input_hash, length=64), "Invalid input sub-block hash {} .. " \
                                                         "expected 64 char hex string".format(self.input_hash)

    @classmethod
    def create(cls, input_hash: str):
        """
        Block manager create a customer AlignInputHash message for each sub-block builder
        :param input_hash: The hash of input bag containing raw txns in order
        :return: A AlignInputHash object
        """
        struct = subblock_capnp.AlignInputHash.new_message()
        struct.inputHash = input_hash

        return cls.from_data(struct)


    @classmethod
    def _chunks(cls, l, n=64):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return subblock_capnp.AlignInputHash.from_bytes_packed(data)

    @lazy_property
    def input_hash(self) -> str:
        return self._data.inputHash.decode()

    def __eq__(self, other):
        assert isinstance(other, AlignInputHash), "Attempted to compare a BlockBuilder with a non-BlockBuilder"
        return self.input_hash == other.input_hash 

    def __repr__(self):
        return "AlignInputHash with\tinput_hash={}" \
               .format(self.input_hash)


class AlignInputHashBuilder:
    @classmethod
    def create(cls, input_hash='A' * 64):
        sbc = AlignInputHash.create(input_hash=input_hash)
        return sbc
