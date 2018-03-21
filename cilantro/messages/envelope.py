from typing import Type
from cilantro.messages import MessageBase
import capnp
import message_capnp


class Envelope(MessageBase):
    """
    All messages passed between nodes must be wrapped in an envelope.

    An envelope specifies what type of message is contained within, as well as metadata possibly such as
    sender signature, timestamp, ect
    """

    def validate(self):
        pass
        assert self._data.type in MessageBase.registry, "Message type {} not found in registry {}"\
                                                        .format(self._data.type, MessageBase.registry)
        # also assert if we can deserialize self._data.payload?

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return message_capnp.Message.from_bytes_packed(data)

    @classmethod
    def create(cls, message: MessageBase):
        """
        Creates a new envelope for a message
        :param message: The MessageBase instance the data payload will store
        :return: An instance of Envelope
        """
        assert issubclass(type(message), MessageBase), "Message arg {} must be a subclass of MessageBase".format(type(message))
        assert type(message) in MessageBase.registry, "Message {} not in registry {}".format(message, MessageBase.registry)

        struct = message_capnp.Message.new_message()
        struct.type = MessageBase.registry[type(message)]
        struct.payload = message.serialize()
        msg = cls.from_data(struct)

        return msg

    def open(self) -> MessageBase:
        """
        Open deserializes the message packed inside the envolope and returns it
        :return: The deserialized MessageBase instance
        """
        return MessageBase.registry[self._data.type].from_bytes(self._data.payload)
