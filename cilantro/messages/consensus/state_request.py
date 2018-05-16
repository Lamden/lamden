from cilantro.messages import MessageBase
import json

"""
State Requests are sent from delegates to masternodes. Delegates use this to get the latest state of the block chain.
A delegate may need to do this if it is:
 1) out of consensus
 2) bootstrapping their application
 3) any connection issues that result in missed transactions (which will likely lead to case 1, but not exclusively)
"""

class StateRequest(MessageBase):

    B_NUM = 'block_num'
    B_HASH = 'block_hash'

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return json.loads(data.decode())

    def serialize(self):
        return json.dumps(self._data).encode()