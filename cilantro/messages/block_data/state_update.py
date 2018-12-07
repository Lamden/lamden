from cilantro.messages.base.base_json import MessageBaseJson
from cilantro.messages.base.base import MessageBase
from cilantro.messages.block_data.block_data import BlockData
from cilantro.utils import lazy_property
from typing import List
from cilantro.utils import is_valid_hex

import capnp
import blockdata_capnp


class BlockIndexRequest(MessageBaseJson):
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
        assert block_hash or block_num, "BlockIndexRequest must be created with a block hash or block number"

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


class BlockIndexReply(MessageBaseJson):

    def validate(self):
        # TODO do validation logic here, not in create
        pass

    @classmethod
    def create(cls, block_indices: List[list]):
        # For dev, validate creation
        assert type(block_indices) is list, 'block_indices must be a list of tuples not {}'.format(type(block_indices))
        for t in block_indices:
            assert type(t) in (list, tuple), "block_indces must be list of tuples, but element found of type {}".format(type(t))
            assert len(t) is 3, "tuple must be of length 3 and the form (block hash, block num, list of mn vks)"
            assert is_valid_hex(t[0], 64), "First element of t must be hash, but got {}".format(t[0])
            assert type(t[1]) is int and t[1] > 0, "Second element must be a block num greater than 0, not {}".format(t[1])
            assert type(t[2]) in (list, tuple, set), '3rd element must be a list of masternode vks not {}'.format(t[2])
            for vk in t[2]:
                assert is_valid_hex(vk, 64), "3rd element must be list of valid verifying keys, but got {}".format(vk)

        return cls.from_data(block_indices)

    @property
    def indices(self) -> List[tuple]:
        return self._data


class BlockDataRequest(BlockIndexRequest):
    pass


class StateUpdateReply(MessageBase):

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return blockdata_capnp.StateUpdateReply.from_bytes_packed(data)

    @classmethod
    def create(cls, block_data: BlockData):
        struct = blockdata_capnp.StateUpdateReply.new_message()
        struct.blockData = block_data._data
        return cls.from_data(struct)

    @lazy_property
    def block_data(self) -> BlockData:
        return BlockData.from_data(self._data.blockData)
