from cilantro.messages.base.base import MessageBase


class MakeNextBlock(MessageBase):

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return b'make_next_block'

    @classmethod
    def create(cls):
        return cls.from_data(b'make_next_block')

    def serialize(self):
        return b'make_next_block'
