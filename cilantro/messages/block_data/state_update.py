from cilantro.messages.base.base_json import MessageBaseJson
from cilantro.messages.base.base import MessageBase
from cilantro.messages.block_data.block_data import BlockData
from cilantro.utils import lazy_property
from typing import List

import capnp
import blockdata_capnp


class StateUpdateRequest(MessageBaseJson):
    """
    State Requests are sent from TESTNET_DELEGATES to TESTNET_MASTERNODES. Delegates use this to get the latest state of the block chain.
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
        pass

    @classmethod
    def create(cls, block_num=None, block_hash=None):
        assert block_hash or block_num, "StateUpdateRequest must be created with a block hash or block number"

        data = {}
        if block_num:
            data[cls.B_NUM] = block_num
        if block_hash:
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


class StateUpdateReply(MessageBase):

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return blockdata_capnp.StateUpdateReply.from_bytes_packed(data)

    @classmethod
    def create(cls, block_data: List[BlockData]):
        struct = blockdata_capnp.StateUpdateReply.new_message()
        struct.blockData = [b._data for b in block_data]

        return cls.from_data(struct)

    @lazy_property
    def block_data(self) -> List[BlockData]:
        return [BlockData.from_data(d) for d in self._data.blockData]
