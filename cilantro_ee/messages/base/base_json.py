import json


"""
A convenience class for those that wish to use JSON. Assumes _data is a dictionary, with keys/values
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


"""
encapsulate json data that is sent between nodes.
"""
class MessageBaseJson:

    def __init__(self, data):
        self._data = data

    @classmethod
    def from_bytes(cls, data: bytes):
        """
        Deserializes binary data and uses it as the underlying data for the newly instantiated Message class
        If validate=True, then this method also calls validate on the newly created Message object.
        :param data: The binary data of the underlying data interchange format
        :param validate: If true, this method will also validate the data before returning the message object
        :return: An instance of MessageBase
        """
        model = cls.from_data(cls._deserialize_data(data))
        return model

    @classmethod
    def from_data(cls, data: object):
        """
        Creates a MessageBase directly from the python data object (dict, capnp struct, str, ect).
        If validate=True, then this method also calls validate on the newly created Message object.
        :param data: The object to use as the underlying data format (i.e. Capnp Struct, JSON dict)
        :param validate: If true, this method will also validate the data before returning the message object
        :return: An instance of MessageBase
        """
        model = cls(data)

        return model

    def __repr__(self):
        return str(self._data)

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return json.loads(data.decode(), object_hook=hex_string_to_bytes)

    def serialize(self):
        return json.dumps(self._data, cls=BytesEncoder).encode()

    def __eq__(self, other):
        return self._data == other._data
