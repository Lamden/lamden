from cilantro_ee.messages.base.base import MessageBase
import json


"""
A convenience class for MessageBase classes which wish to use JSON. Assumes _data is a dictionary, with keys/values
that are serialize with json.dumps(...)
"""


class MessageBaseJson(MessageBase):
    @classmethod
    def _deserialize_data(cls, data: bytes):
        return json.loads(data.decode())

    def serialize(self):
        return json.dumps(self._data).encode()

    def __eq__(self, other):
        return self._data == other._data