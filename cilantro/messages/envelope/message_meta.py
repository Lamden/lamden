from cilantro.messages.base.base import MessageBase
from cilantro.constants.protocol import max_uuid
import capnp
import envelope_capnp

import random


class MessageMeta(MessageBase):
    """
    The MessageMeta class is used exclusively inside Envelopes, and is used to specify metadata about the envelope and
    message including:
    - The message's type. This is an enum (an integer) which maps to a MessageBase class using the dict MessageBase.registry
    - The envelope's UUID. This is a unique integer that gets randomly generated when the envelope is created. The
      exception to this is when creating reply envelopes. Reply envelope use the request envelope's UUID, so that nodes
      can independently pair request and replies.
    - The timestamp. This is simply the time the envelope was created.
    """

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return envelope_capnp.MessageMeta.from_bytes_packed(data)

    def validate(self):
        # TODO -- implement
        pass

    @classmethod
    def create(cls, type: int, timestamp: str, uuid: int=-1):
        """
        Creates a MessageMeta. If no uuid is specified, or if uuid=-1, a random UUID is generated.
        :param type: The enum representing a MessageBase class. Must exist in MessageBase.registry
        :param timestamp:
        :param uuid:
        :return:
        """
        assert type in MessageBase.registry, "Type enum {} not found in MessageBase.registry {}"\
                                             .format(type, MessageBase.registry)

        if uuid == -1:
            uuid = random.randint(0, max_uuid)

        data = envelope_capnp.MessageMeta.new_message()
        data.type = type
        data.timestamp = timestamp
        data.uuid = uuid

        return cls.from_data(data)

    @property
    def type(self) -> int:
        return self._data.type

    @property
    def uuid(self) -> int:
        return self._data.uuid

    @property
    def timestamp(self) -> str:
        return self._data.timestamp


