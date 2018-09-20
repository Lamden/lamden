from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property, Hasher
from cilantro.messages.utils import validate_hex
from cilantro.logger import get_logger
from typing import List

import capnp
import subblock_capnp

log = get_logger(__name__)

# class SubBlock(MessageBase):
#     def validate(self):
#         #TODO
#         pass
#
#     @classmethod
#     def _deserialize_data(cls, data: bytes):
#         return subblock_capnp.SubBlock.from_bytes_packed(data)
#
#     @classmethod
#     def create(cls, signatures: List[str], merkle_leaves: List[str]):
#         """
#         Creates a TransactionReply object from a list of ContractTransaction binaries.
#         :param raw_transactions: A list of ContractTransaction binaries
#         :return: A TransactionReply object
#         """
#         struct = subblock_capnp.SubBlock.new_message()
#         struct.init('signatures', len(signatures))
#         struct.init('merkleLeaves', len(merkle_leaves))
#         struct.signatures = signatures
#         struct.merkleLeaves = merkle_leaves
#         return cls.from_data(struct)

class SubBlockHashes(MessageBase):
    """
        SubBlockHashes is the combined root hashes of each sub-block. This is sent to other master
        nodes in order to confirm that they have the same combined result hash; thereby, should store
        the corresponding sub-blocks into the block-chain.
    """

    def validate(self):
        self.sub_block_hashes

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return subblock_capnp.SubBlockHashes.from_bytes_packed(data)

    @classmethod
    def create(cls, sub_block_hashes: List[str]):
        """
        Creates a TransactionReply object from a list of ContractTransaction binaries.
        :param raw_transactions: A list of ContractTransaction binaries
        :return: A TransactionReply object
        """
        sbh = sorted(sub_block_hashes)
        struct = subblock_capnp.SubBlockHashes.new_message()
        struct.init('subBlockHashes', len(sbh))
        struct.subBlockHashes = sbh
        return cls.from_data(struct)

    @lazy_property
    def full_block_hash(self) -> str:
        return Hasher.hash_iterable(self._data.subBlockHashes)

    @lazy_property
    def sub_block_hashes(self) -> List[str]:
        return [h.hex() for h in self._data.subBlockHashes]
