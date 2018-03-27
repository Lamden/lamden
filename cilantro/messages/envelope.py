from typing import Type
from cilantro.messages import MessageBase
from random import randint
import capnp
import envelope_capnp


"""
Sender hashes payload and sets that to the transactions UUID (or should we generate random?)
Sends signs payload

Signature is checked when opened



When updating state, just calculate the diffs between block numbers 


"""

MAX_UUID = pow(2, 32)


class Envelope(MessageBase):
    """
    All messages passed between nodes must be wrapped in an envelope.

    An envelope specifies what type of message is contained within, as well as metadata possibly such as
    sender signature, timestamp, ect
    """

    def validate(self):
        assert self._data.type in MessageBase.registry, "Message type {} not found in registry {}"\
                                                        .format(self._data.type, MessageBase.registry)
        # also assert if we can deserialize self._data.payload?

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return envelope_capnp.Envelope.from_bytes_packed(data)

    @classmethod
    def create(cls, message: MessageBase):
        """
        Creates a new envelope for a message
        :param message: The MessageBase instance the data payload will store
        :return: An instance of Envelope
        """
        assert issubclass(type(message), MessageBase), "Message arg {} must be a subclass of MessageBase".format(type(message))
        assert type(message) in MessageBase.registry, "Message {} not in registry {}".format(message, MessageBase.registry)

        struct = envelope_capnp.Envelope.new_message()
        struct.type = MessageBase.registry[type(message)]
        struct.signature = b'TODO: SIGNATURE'
        struct.uuid = randint(0, MAX_UUID)
        struct.payload = message.serialize()
        msg = cls.from_data(struct)

        return msg

    def open(self, validate=True) -> MessageBase:
        """
        Open deserializes the message packed inside the envelope and returns it
        :return: The deserialized MessageBase instance
        """
        # TODO vallidate signature of payload
        return MessageBase.registry[self._data.type].from_bytes(self._data.payload)
