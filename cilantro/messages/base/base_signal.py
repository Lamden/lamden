from cilantro.messages.base.base import MessageBase


class SignalBase(MessageBase):

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return cls.__name__.encode()

    @classmethod
    def create(cls):
        return cls.from_data(cls.__name__.encode())

    def serialize(self):
        return type(self).__name__.encode()

    def __eq__(self, other):
        return type(self) == type(other)
