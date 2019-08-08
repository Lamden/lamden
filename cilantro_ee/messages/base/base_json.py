from cilantro_ee.messages.base.base import MessageBase
import json


"""
A convenience class for MessageBase classes which wish to use JSON. Assumes _data is a dictionary, with keys/values
that are serialize with json.dumps(...)
"""


class BytesEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            return {'__bytes__': obj.hex()}
        return obj


def hex_string_to_bytes(obj):
    if '__bytes__' in obj:
        return bytes.fromhex(obj['__bytes__'])
    return obj


class MessageBaseJson(MessageBase):
    @classmethod
    def _deserialize_data(cls, data: bytes):
        return json.loads(data.decode(), object_hook=hex_string_to_bytes)

    def serialize(self):
        return json.dumps(self._data, cls=BytesEncoder).encode()

    def __eq__(self, other):
        return self._data == other._data