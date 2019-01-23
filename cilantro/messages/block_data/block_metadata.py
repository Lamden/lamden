from cilantro.messages.base.base import MessageBase
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.utils import validate_hex
from cilantro.messages.block_data.sub_block import SubBlock
from cilantro.utils import lazy_property
from cilantro.constants.system_config import NUM_SB_PER_BLOCK
from cilantro.storage.vkbook import VKBook
import time
from typing import List

import capnp
import blockdata_capnp


class BlockMetaData(BlockData):
    """
    BlockMetaData is basically the same as BlockData, except it does not contain the actual transactions or
    the Merkle leaves. This makes it waaaay smaller when sent over the wire.
    """
    pass

    def validate(self):
        super().validate()

        # This is just for dev purposes. We check that no one is trying to create this with actual transactions
        # or merkle leaves (use a an ctual BlockData or BlockDataReply for this)
        assert len(self.transactions) == 0, "BlockMetaData should not contain any transactions!"
        assert len(self.merkle_leaves) == 0, "BlockMetaData should not contain any merkle_leaves!"

    @classmethod
    def create_from_block_data(cls, data: BlockData):
        # Remove the transactions and merkle leaves first
        for sb in data.sub_blocks:
            sb.remove_tx_data()

        return cls.from_data(data._data)


class NewBlockNotification(BlockMetaData):
    pass


class SkipBlockNotification(BlockMetaData):
    pass

    def validate(self):
        pass     # don't worry about it for now

    @classmethod
    def create_from_sub_blocks(cls, prev_block_hash: str, block_num: int, sub_blocks: List[SubBlock]):
        # Sort sub-blocks by index if they are not done so already
        sub_blocks = sorted(sub_blocks, key=lambda sb: sb.index)

        roots = [sb.input_hash for sb in sub_blocks]
        block_hash = BlockData.compute_block_hash(sbc_roots=roots, prev_block_hash=prev_block_hash)

        return cls.create(block_hash, prev_block_hash, [], block_num, sub_blocks)
