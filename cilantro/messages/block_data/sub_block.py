from cilantro.messages.base.base import MessageBase
from cilantro.utils import lazy_property, Hasher
from cilantro.messages.utils import validate_hex
from cilantro.logger import get_logger
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.transaction.data import TransactionData
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
        if len(self.transactions) > 0:
            assert len(self.transactions) == len(
                self.merkle_leaves), "Length of transactions transactions {} does not match length of merkle leaves {}".format(
                len(self.transactions), len(self.merkle_leaves))

        # TODO validate signatures

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return subblock_capnp.SubBlock.from_bytes_packed(data)

    @classmethod
    def create(cls, merkle_root: str, signatures: List[MerkleSignature], merkle_leaves: List[str], sub_block_idx: int,
               input_hash: str, transactions: List[TransactionData]=None):
        # Validate input (for dev)
        for s in signatures:
            assert isinstance(s, MerkleSignature), "'signatures' arg must be a list of signatures, not {}".format(s)
        for t in transactions:
            assert isinstance(t, TransactionData), "'transactions' must be a list of TransactionData instances, not {}".format(tx)

        struct = subblock_capnp.SubBlock.new_message()
        struct.signatures = [sig.serialize() for sig in signatures]
        struct.merkleLeaves = merkle_leaves
        struct.merkleRoot = merkle_root
        struct.subBlockIdx = sub_block_idx
        struct.inputHash = input_hash
        struct.transactions = [tx._data for tx in transactions]
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

    @lazy_property
    def transactions(self) -> List[TransactionData]:
        return [TransactionData.from_data(tx) for tx in self._data.transactions]
