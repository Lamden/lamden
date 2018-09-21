from cilantro.messages.base.base_json import MessageBaseJson
from typing import List


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


# TODO -- write unit tests for this guy
class StateUpdateReply(MessageBaseJson):
    """
    A StateUpdateReply contains all the transactions in a particular block. This information is stored in the 'payload'
    property, which represents the leaves of the block's merkle tree (stored as transaction binaries).
    """

    B_NUM = 'block_num'
    B_HASH = 'block_hash'
    B_PAYLOAD = 'block_payload'

    def validate(self):
        pass

    @classmethod
    def create(cls, payload: list, block_num=None, block_hash=None):
        assert block_hash or block_num, "StateUpdateReply must be created with a block hash or block number"

        data = {cls.B_PAYLOAD: payload}

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

    @property
    def payload(self) -> List[bytes]:
        """
        The block transaction payload. This is a list of transactions, which represented the leaves of a merkle tree.
        """
        return self._data[self.B_PAYLOAD]
