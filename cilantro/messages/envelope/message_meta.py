from cilantro import Constants
from cilantro.messages import MessageBase
import capnp
import envelope_capnp

import random


class MessageMeta(MessageBase):
    @classmethod
    def _deserialize_data(cls, data: bytes):
        return envelope_capnp.MessageMeta.from_bytes_packed(data)

    def validate(self):
        # TODO -- implement
        pass

    @classmethod
    def create(cls, type: int, timestamp: str, uuid: int=-1):
        if uuid == -1:
            uuid = random.randint(0, Constants.Protocol.MaxUuid)

        data = envelope_capnp.MessageMeta.new_message()
        data.type = type
        data.timestamp = timestamp
        data.uuid = uuid

        return cls.from_data(data)

    @property
    def type(self):
        return self._data.type

    @property
    def uuid(self):
        return self._data.uuid

    @property
    def timestamp(self):
        return self._data.timestamp


