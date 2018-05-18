from cilantro.messages import MessageBaseJson
import json

"""
State Requests are sent from delegates to masternodes. Delegates use this to get the latest state of the block chain.
A delegate may need to do this if it is:
 1) out of consensus
 2) bootstrapping their application
 3) any connection issues that result in missed transactions (which will likely lead to case 1, but not exclusively)
"""


class StateRequest(MessageBaseJson):

    B_NUM = 'block_num'
    B_HASH = 'block_hash'

    def validate(self):
        pass

    @classmethod
    def create(cls, current_block_num=None, current_block_hash=None):
        data = {}
        if current_block_num:
            data[cls.B_NUM] = current_block_num
        if current_block_hash:
            data[cls.B_HASH] = current_block_hash

        return cls.from_data(data)

    @property
    def current_block_num(self):
        return self._data.get(self.B_NUM)

    @property
    def current_block_hash(self):
        return self._data.get(self.B_HASH)



