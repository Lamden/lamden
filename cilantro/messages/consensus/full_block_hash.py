from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property, Hasher
from cilantro.messages.utils import validate_hex
from cilantro.logger import get_logger

import capnp
import consensus_capnp

log = get_logger(__name__)

class FullBlockHash(MessageBase):
    """
        FullBlockHash is the combined root hashes of each sub-block. This is sent to other master
        nodes in order to confirm that they have the same combined result hash; thereby, should store
        the corresponding sub-blocks into the block-chain.
    """

    def validate(self):
        assert validate_hex(self._data.fullBlockHash)
        self.full_block_hash

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return consensus_capnp.FullBlockHash.from_bytes_packed(data)

    @classmethod
    def create(cls, full_block_hash: str):
        """
        Creates a TransactionReply object from a list of ContractTransaction binaries.
        :param raw_transactions: A list of ContractTransaction binaries
        :return: A TransactionReply object
        """
        struct = consensus_capnp.FullBlockHash.new_message()
        struct.fullBlockHash = Hasher.hash(full_block_hash)
        return cls.from_data(struct)

    @lazy_property
    def full_block_hash(self) -> str:
        return self._data.fullBlockHash.decode()
