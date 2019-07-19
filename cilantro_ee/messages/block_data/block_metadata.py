from cilantro_ee.messages.block_data.block_data import BlockData
from cilantro_ee.messages.block_data.sub_block import SubBlock
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

