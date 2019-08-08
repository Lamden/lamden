from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.utils import lazy_property
from cilantro_ee.messages.block_data.sub_block import SubBlock
from cilantro_ee.messages.utils import validate_hex
from cilantro_ee.messages.block_data.block_data import BlockData
from typing import List

import notification_capnp


class BlockNotification(MessageBase):
    pass

class ConsensusBlockNotification(BlockNotification):

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data):
        return notification_capnp.ConsensusBlockNotification.from_bytes_packed(data)

    @classmethod
    def from_dict(cls, data: dict):
        struct = notification_capnp.ConsensusBlockNotification.new_message(**data)
        return cls.from_data(struct)

    @classmethod
    def create(cls, prev_block_hash: str, block_hash: str, block_num: int,
               first_sb_idx: int, block_owners: List[str], input_hashes: List[str]):

        struct = notification_capnp.ConsensusBlockNotification.new_message()
        struct.prevBlockHash = prev_block_hash
        struct.blockHash = block_hash
        struct.blockNum = block_num
        struct.firstSbIdx = first_sb_idx
        struct.blockOwners = [block_owner for block_owner in block_owners]
        struct.inputHashes = input_hashes

        return cls.from_data(struct, False)    # no validation

    @classmethod
    def get_data_from_sub_blocks(cls, sub_blocks: List[SubBlock]):
        input_hashes = []
        root_hashes = []
        for sb in sub_blocks:
            input_hashes.append(sb.inputHash)
            if not len(sb.merkleLeaves) == 0:
                root_hashes.append(sb.resultHash)
        return input_hashes, root_hashes


    @classmethod
    def create_from_sub_blocks(cls, prev_block_hash: str, block_num: int, block_owners: List[str], sub_blocks):
        # Sort sub-blocks by index if they are not done so already  - TODO eliminate it by ensuring they come in sorted
        sub_blocks = sorted(sub_blocks, key=lambda sb: sb.subBlockIdx)

        input_hashes, root_hashes = cls.get_data_from_sub_blocks(sub_blocks)

        first_sb_idx = sub_blocks[0].subBlockIdx
        roots = root_hashes if root_hashes else input_hashes
        block_hash = BlockData.compute_block_hash(sbc_roots=roots, prev_block_hash=prev_block_hash)

        return cls.create(prev_block_hash, block_hash, block_num, first_sb_idx, block_owners, input_hashes)

    @property
    def prev_block_hash(self) -> str:
        return self._data.prevBlockHash

    @property
    def block_hash(self) -> str:
        return self._data.blockHash

    @property
    def block_num(self) -> int:
        return self._data.blockNum

    @property
    def first_sb_index(self) -> int:
        return self._data.firstSbIdx

    @lazy_property
    def block_owners(self) -> List[str]:
        # Necessary to cast capnp list builder to Python list
        return [x for x in self._data.blockOwners]

    @lazy_property
    def input_hashes(self) -> List[str]:
        # Necessary to cast capnp list builder to Python list
        return [x for x in self._data.inputHashes]

    def __repr__(self):
        # return "<{} (block_hash={}, block_num={}, prev_b_hash={}, input_hashes={}, block_owners={})>"\
            # .format(type(self), self.block_hash, self.block_num, self.prev_block_hash, self.input_hashes, self.block_owners))
        return f"{type(self)} (block_hash={self.block_hash}, block_num={self.block_num}, \
                 prev_b_hash={self.prev_block_hash}, input_hashes={self.input_hashes}, block_owners={self.block_owners})>"


class NewBlockNotification(ConsensusBlockNotification):
    pass

class SkipBlockNotification(ConsensusBlockNotification):
    pass

class FailedBlockNotification(BlockNotification):

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data):
        return notification_capnp.FailedBlockNotification.from_bytes_packed(data)

    @classmethod
    def from_dict(cls, data: dict):
        struct = notification_capnp.FailedBlockNotification.new_message(**data)
        return cls.from_data(struct)

    @classmethod
    def create(cls, prev_block_hash: str, block_hash: str, block_num: int,
               first_sb_idx: int, input_hashes: List[List]):

        struct = notification_capnp.FailedBlockNotification.new_message()
        struct.prevBlockHash = prev_block_hash
        struct.blockHash = block_hash
        struct.blockNum = block_num
        struct.firstSbIdx = first_sb_idx
        struct.inputHashes = input_hashes

        return cls.from_data(struct, False)    # no validation


    @property
    def prev_block_hash(self):
        return self._data.prevBlockHash

    @property
    def block_hash(self) -> str:
        return self._data.blockHash

    @property
    def block_num(self) -> int:
        return self._data.blockNum

    @property
    def first_sb_index(self) -> int:
        return self._data.firstSbIdx

    @lazy_property
    def input_hashes(self) -> List[List]:
        # Necessary to cast capnp list builder to Python list
        return [[x for x in sl] for sl in self._data.inputHashes]
