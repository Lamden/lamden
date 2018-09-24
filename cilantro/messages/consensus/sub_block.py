from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property, Hasher
from cilantro.messages.utils import validate_hex
from cilantro.logger import get_logger
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from typing import List

import capnp
import subblock_capnp

log = get_logger(__name__)

class SubBlockMetaData(MessageBase):
    def validate(self):
        assert self._data.signatures
        assert self._data.merkleLeaves
        assert self._data.merkleRoot
        assert type(self._data.subBlockIdx) == int

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return subblock_capnp.SubBlock.from_bytes_packed(data)

    @classmethod
    def create(cls, merkle_root: str, signatures: List[str], merkle_leaves: List[str], sub_block_idx: int):
        struct = subblock_capnp.SubBlock.new_message()
        struct.init('signatures', len(signatures))
        struct.init('merkleLeaves', len(merkle_leaves))
        struct.signatures = list(signatures)
        struct.merkleLeaves = list(merkle_leaves)
        struct.merkleRoot = merkle_root
        struct.subBlockIdx = sub_block_idx
        return cls.from_data(struct)

    @lazy_property
    def signatures(self) -> List[MerkleSignature]:
        return [MerkleSignature.from_bytes(sig) for sig in self._data.signatures]

    @lazy_property
    def merkleLeaves(self) -> List[str]:
        return [leaf.hex() for leaf in self._data.merkleLeaves]

    @property
    def merkle_root(self) -> str:
        return self._data.merkleRoot.hex()

    @property
    def sub_block_idx(self) -> int:
        return int(self._data.subBlockIdx)

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
