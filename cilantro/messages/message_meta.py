from cilantro.messages import MessageBase
import capnp
import messagemeta_capnp

import random


MAX_UUID = pow(2, 32)


class MessageMeta(MessageBase):
    @classmethod
    def _deserialize_data(cls, data: bytes):
        return messagemeta_capnp.MessageMeta.from_bytes_packed(data)

    def validate(self):
        # TODO -- implement
        pass

    @classmethod
    def create(cls, type: int, signature: bytes, sender: str, timestamp: str, uuid: int=-1):
        if uuid == -1:
            uuid = random.randint(0, MAX_UUID)

        data = messagemeta_capnp.MessageMeta.new_message()
        data.type = type
        data.signature = signature
        data.timestamp = timestamp
        data.uuid = uuid
        data.sender = sender

        return cls.from_data(data)

    @property
    def type(self):
        return self._data.type

    @property
    def uuid(self):
        return self._data.uuid

    @property
    def signature(self):
        return self._data.signature

    @property
    def timestamp(self):
        return self._data.timestamp.decode()

    @property
    def sender(self):
        return self._data.sender.decode()