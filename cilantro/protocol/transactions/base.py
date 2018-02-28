from .builder import TransactionBuilder

from cilantro import Constants

JSON = {
    'payload': None,
    'proof': None,
    'signature': None
}


class Transaction:
    @staticmethod
    def serialize(data):
        return Constants.Protocol.Serialization.serialize(data)

    @staticmethod
    def deserialize(data):
        return Constants.Protocol.Serialization.deserialize(data)

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
