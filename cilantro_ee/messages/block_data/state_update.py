from cilantro_ee.messages.base.base_json import MessageBaseJson
from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.messages.block_data.block_data import BlockData
from cilantro_ee.utils import lazy_property
from typing import List
from cilantro_ee.utils import is_valid_hex
from cilantro_ee.constants.system_config import NUM_SUB_BLOCKS

import capnp
import blockdata_capnp


class BlockIndexRequest(MessageBaseJson):
    """
    State Requests are sent from delegates to masternodes. Delegates use this to get the latest state of the block chain.
    A delegate may need to do this if it is:
     1) out of consensus
     2) bootstrapping their application
     3) any connection issues that result in missed transactions (which will likely lead to case 1, but not exclusively)
    Additionally, a master may need to do this if it is:
     1) out of consensus with other masternodes
    """

    B_NUM = 'block_num'
    B_HASH = 'block_hash'

    def validate(self):
        if self.block_hash is not None:
            assert is_valid_hex(self.block_hash), "Not valid hash: {}".format(self.block_hash)
        assert self.block_hash is not None or self.block_num is not None, "must provide block hash or num"

    @classmethod
    def create(cls, block_num=None, block_hash=None):
        assert block_hash or block_num is not None, "BlockIndexRequest must be created with a block hash or block number"

        data = {}
        if block_num is not None:
            data[cls.B_NUM] = block_num
        if block_hash is not None:
            data[cls.B_HASH] = block_hash

        return cls.from_data(data)

    @property
    def block_num(self) -> int:
        """
        The block number to request data for
        """
        return self._data.get(self.B_NUM)

    @property
    def block_hash(self) -> str:
        """
        The block hash to request data for
        """
        return self._data.get(self.B_HASH)

    def __eq__(self, other):
        assert type(other) is type(self), "Cannot compare {} with type {}".format(type(self), type(other))
        return self.block_num == other.block_num or self.block_hash == other.block_hash


class BlockIndexReply(MessageBaseJson):
    def validate(self):
        # TODO do validation logic here, not in create
        pass

    @classmethod
    def create(cls, block_info: List[dict]):
        return cls.from_data(block_info)

    @property
    def indices(self) -> List[dict]:
        return self._data


class BlockDataRequest(BlockIndexRequest):
    pass


class BlockDataReply(BlockData):

    @classmethod
    def create_from_block(cls, block: BlockData):
        return cls.from_data(block._data)

