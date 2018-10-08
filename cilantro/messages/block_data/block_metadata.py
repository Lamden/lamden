from cilantro.messages.base.base import MessageBase
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.utils import validate_hex
from cilantro.utils import lazy_property
from cilantro.constants.system_config import NUM_SB_PER_BLOCK
from cilantro.storage.db import VKBook
import time
from typing import List

import capnp
import blockdata_capnp


class BlockMetaData(MessageBase):
    """
    This class is the metadata for combined validated sub blocks.
    """

    def validate(self):
        from cilantro.messages.block_data.block_data import BlockData  # avoid cyclic imports

        assert validate_hex(self._data.blockHash, 64), 'Invalid hash'
        assert validate_hex(self._data.prevBlockHash, 64), 'Invalid previous block hash'
        assert len(self._data.merkleRoots) == NUM_SB_PER_BLOCK, 'num of roots in block meta {} does not match ' \
                                                                'NUM_SB_PER_BLOCK {}'.format(len(self._data.merkleRoots),
                                                                                             NUM_SB_PER_BLOCK)
        assert type(self._data.timestamp) == int, 'Invalid timestamp'
        assert self.masternode_signature.sender in VKBook.get_masternodes(), 'Not a valid masternode'
        assert self.masternode_signature.verify(self.block_hash.encode()), 'Cannot verify signature'
        expected_b_hash = BlockData.compute_block_hash(sbc_roots=self.merkle_roots, prev_block_hash=self.prev_block_hash)
        assert expected_b_hash == self.block_hash, "Block hash could not be verified (does not match computed hash)"

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return blockdata_capnp.BlockMetaData.from_bytes_packed(data)

    @classmethod
    def create(cls, block_hash: str, merkle_roots: List[str], prev_block_hash: str,
               masternode_signature: MerkleSignature, timestamp: int=0, block_num: int=0, input_hashes: List[str]=None):

        if not timestamp:
            timestamp = int(time.time())

        struct = blockdata_capnp.BlockMetaData.new_message()
        struct.init('merkleRoots', len(merkle_roots))
        struct.blockHash = block_hash
        struct.merkleRoots = merkle_roots
        struct.inputHashes = input_hashes
        struct.prevBlockHash = prev_block_hash
        struct.timestamp = int(timestamp)
        struct.blockNum = block_num
        struct.masternodeSignature = masternode_signature.serialize()
        return cls.from_data(struct)

    @property
    def block_hash(self) -> str:
        return self._data.blockHash.decode()

    @property
    def merkle_roots(self) -> List[str]:
        return [root.decode() for root in self._data.merkleRoots]

    @property
    def input_hashes(self) -> List[str]:
        return [h.decode() for h in self._data.inputHashes]

    @property
    def masternode_signature(self) -> MerkleSignature:
        return MerkleSignature.from_bytes(self._data.masternodeSignature)

    @property
    def prev_block_hash(self) -> str:
        return self._data.prevBlockHash.decode()

    @property
    def timestamp(self) -> int:
        return self._data.timestamp

    @property
    def block_num(self) -> int:
        return self._data.blockNum

    def __eq__(self, other):
        return self._data.blockHash == other._data.blockHash and \
            self.merkle_roots == other.merkle_roots


class NewBlockNotification(BlockMetaData):
    def validate(self):
        super().validate()
        assert len(self._data.inputHashes) == len(self._data.merkleRoots), "Length of input hashes does not match " \
                                                                           "length of merkle roots"

