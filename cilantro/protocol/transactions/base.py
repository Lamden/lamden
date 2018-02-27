from .constants import *
from .builder import TransactionBuilder

JSON = {
    'payload': None,
    'proof': None,
    'signature': None
}


class Transaction:
    @staticmethod
    def serialize(data):
        return SERIALIZER.serialize(data)

    @staticmethod
    def deserialize(data):
        return SERIALIZER.deserialize(data)

    @staticmethod
    def from_json(data):
        pass

    @staticmethod
    def new():
        return {
            'payload': None,
            'proof': None,
            'signature': None
        }

    @staticmethod
    def is_valid(data):
        pass
