from cilantro import Constants
from cilantro.messages import MessageMeta, MessageBase
import capnp
import envelope_capnp
import time

"""
Sender hashes payload and sets that to the transactions UUID (or should we generate random?)
Sends signs payload

Signature is checked when opened



When updating state, just calculate the diffs between block numbers 


"""

# class Envelope(MessageBase):
#     """
#     All messages passed between nodes must be wrapped in an envelope.
#
#     An envelope specifies what type of message is contained within, as well as metadata possibly such as
#     sender signature, timestamp, ect
#     """
#
#     def validate(self):
#         assert self._data.type in MessageBase.registry, "Message type {} not found in registry {}"\
#                                                         .format(self._data.type, MessageBase.registry)
#         # TODO -- check signature?
#
#     @classmethod
#     def _deserialize_data(cls, data: bytes):
#         return envelope_capnp.Envelope.from_bytes_packed(data)
#
#     @classmethod
#     def create(cls, message: MessageBase, uuid=None):
#         """
#         Creates a new envelope for a message
#         :param message: The MessageBase instance the data payload will store
#         :return: An instance of Envelope
#         """
#         assert issubclass(type(message), MessageBase), "Message arg {} must be a subclass of MessageBase".format(type(message))
#         assert type(message) in MessageBase.registry, "Message {} not in registry {}".format(message, MessageBase.registry)
#
#         struct = envelope_capnp.Envelope.new_message()
#         struct.type = MessageBase.registry[type(message)]
#         struct.signature = b'TODO: SIGNATURE'
#         if uuid is None:
#             struct.uuid = randint(0, MAX_UUID)
#         else:
#             struct.uuid = uuid
#         struct.payload = message.serialize()
#         msg = cls.from_data(struct)
#
#         return msg
#
#     def open(self, validate=True) -> MessageBase:
#         """
#         Open deserializes the message packed inside the envelope and returns it
#         :return: The deserialized MessageBase instance
#         """
#         # TODO vallidate signature of payload
#         return MessageBase.registry[self._data.type].from_bytes(self._data.payload)
#
#     @property
#     def uuid(self):
#         return self._data.uuid


class Envelope:
    """
    An envelope is a convenience wrapper around a message's metadata (MessageMeta) and its
    payload (MessageBase subclass).

    This class provides API for
        - MessageMeta creation, which includes payload signing, time stamping, and uuid generation
        - signature verification
        - payload deserialization

    All ZMQ envelopes are formed with 3 frames:
    1. Header -- a filter frame for Sub/Pub or an id frame for Dealer/Router. This is included as raw binary in a zmq
                 frame, and is not wrapped in a capnp struct or any custom serialization format.
    2. Metadata -- MessageMeta binary, which includes fields: type, uuid, signature, timestamp, and sender
    3. Payload  -- a serialized MessageBase subclass, i.e. StandardTransaction or BlockContender

    Note to self:
    You want to create this class with an existing message meta instance, or without one by passing in keyword values
    and such.
    - It will be created from a messagebase instance when a new message created and sent
    - It will be created from binary metadata and bytes when recv_multipart'd
      from a zmq socket, and check the the message meta will be used for message duplication/sig validation, and
    the
    """

    @classmethod
    def from_bytes(cls, payload: bytes, message_meta: bytes):
        return cls(message_meta, payload)

    @classmethod
    def from_data(cls, signing_key: str, sender: str, payload: MessageBase):
        payload_binary = payload.serialize()
        payload_type = MessageBase.registry[type(payload)]
        signature = Constants.Protocols.Wallets.sign(signing_key, payload_binary)
        timestamp = time.time()

        msg_meta = MessageMeta.create(type=payload_type, signature=signature, sender=sender, timestamp=str(timestamp))
        return cls(msg_meta, payload_binary)

    def __init__(self, metadata: bytes, payload: bytes):
        self._payload, self._metadata = None, None
        self._metadata_binary = metadata
        self._payload_binary = payload

    def verify_signature(self, verifying_key: str):
        return Constants.Protocols.Wallets.verify(verifying_key, self._payload_binary, self.metadata.signature)

    @property
    def payload(self) -> MessageBase:
        if not self._payload:
            print("Lazy instantiating payload...")  # debug line, remove later
            self._payload = MessageBase.registry[self.metadata.type].from_bytes(self._payload_binary)
            print("Made payload: {}".format(self._payload))  # debug line, remove later
        return self._payload

    @property
    def metadata(self) -> MessageMeta:
        if not self._metadata:
            print("Lazy instantiating metadata...")  # debug line, remove later
            self._metadata = MessageMeta.from_bytes(self._metadata_binary)
            print("Made metadata: {}".format(self._metadata))  # debug line, remove later
        return self._metadata








