from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property, Hasher
from cilantro.messages.utils import validate_hex
from cilantro.logger import get_logger
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from typing import List

import capnp
import subblock_capnp

log = get_logger(__name__)


class SubBlock(MessageBase):
    def validate(self):
        validate_hex(self.merkle_root, length=64, field_name='merkle_root')
        validate_hex(self.input_hash, length=64, field_name='input_hash')
        assert self._data.signatures
        assert self._data.merkleLeaves
        assert type(self._data.subBlockIdx) == int

        # TODO validate signatures

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return subblock_capnp.SubBlock.from_bytes_packed(data)

    @classmethod
    def create(cls, merkle_root: str, signatures: List[MerkleSignature], merkle_leaves: List[str], sub_block_idx: int,
               input_hash: str):
        for s in signatures:
            assert isinstance(s, MerkleSignature), "'signatures' arg must be a list of signatures, not {}".format(s)

        struct = subblock_capnp.SubBlock.new_message()
        struct.signatures = [sig.serialize() for sig in signatures]
        struct.merkleLeaves = merkle_leaves
        struct.merkleRoot = merkle_root
        struct.subBlockIdx = sub_block_idx
        struct.inputHash = input_hash
        return cls.from_data(struct)

    @lazy_property
    def signatures(self) -> List[MerkleSignature]:
        return [MerkleSignature.from_bytes(sig) for sig in self._data.signatures]

    @lazy_property
    def merkle_leaves(self) -> List[str]:
        return [leaf for leaf in self._data.merkleLeaves]

    @property
    def merkle_root(self) -> str:
        return self._data.merkleRoot

    @property
    def input_hash(self) -> str:
        return self._data.inputHash

    @property
    def sub_block_idx(self) -> int:
        return int(self._data.subBlockIdx)
