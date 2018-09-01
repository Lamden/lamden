from cilantro.messages.base.base import MessageBase


class KillSignal(MessageBase):

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return b''

    @classmethod
    def create(cls):
        return cls.from_data(b'')

    def serialize(self):
        return b''