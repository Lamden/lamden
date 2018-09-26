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
