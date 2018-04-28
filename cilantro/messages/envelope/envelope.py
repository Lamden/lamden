from cilantro import Constants
from cilantro.utils import lazy_property, set_lazy_property
from cilantro.messages import MessageMeta, MessageBase, Seal
from cilantro.protocol.structures import EnvelopeAuth
import time

import capnp
import envelope_capnp


class Envelope(MessageBase):

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return envelope_capnp.Envelope.from_bytes_packed(data)

    # TODO -- method to create a message with an envelope (i.e. preset uuid?)
    @classmethod
    def create_from_message(cls, message: MessageBase, signing_key: str, sender_id: str, verifying_key: str=None):
        assert issubclass(type(message), MessageBase), "message arg must be a MessageBase subclass"
        assert type(message) in MessageBase.registry, "Message type {} not found in registry {}"\
            .format(type(message), MessageBase.registry)
        # TODO -- verify sk (valid hex, 128 char)

        # Create MessageMeta
        t = MessageBase.registry[type(message)]
        timestamp = str(time.time())
        meta = MessageMeta.create(type=t, sender=sender_id, timestamp=timestamp)

        # Create Seal
        if not verifying_key:
            verifying_key = Constants.Protocol.Wallets.get_vk(signing_key)
        seal_sig = EnvelopeAuth.seal(signing_key=signing_key, meta=meta, message=message)
        seal = Seal.create(signature=seal_sig, verifying_key=verifying_key)

        # Create Envelope
        obj = cls.create_from_objects(seal=seal, meta=meta, message=message.serialize())
        set_lazy_property(obj, 'message', message)

        return obj

    @classmethod
    def create_from_objects(cls, seal: Seal, meta: MessageMeta, message: bytes):
        data = envelope_capnp.Envelope.new_message()
        data.seal = seal._data
        data.meta = meta._data
        data.message = message

        obj = cls.from_data(data)

        set_lazy_property(obj, 'seal', seal)
        set_lazy_property(obj, 'meta', meta)

        return obj

    def validate(self):
        # TODO -- implement
        # Try to access .seal/.meta./.message to make sure they deserialize properly
        pass

    def verify_seal(self):
        return EnvelopeAuth.verify_seal(seal=self.seal, meta=self.meta_binary, message=self.message_binary)

    @property
    def message_binary(self) -> bytes:
        return self._data.message

    @lazy_property
    def meta_binary(self) -> bytes:
        return self.meta.serialize()

    @lazy_property
    def seal(self) -> Seal:
        return Seal.from_data(self._data.seal)

    @lazy_property
    def meta(self) -> MessageMeta:
        return MessageMeta.from_data(self._data.meta)

    @lazy_property
    def message(self) -> MessageBase:
        assert self.meta.type in MessageBase.registry, "Type {} not found in registry {}"\
            .format(self.meta.type, MessageBase.registry)

        return MessageBase.registry[self.meta.type].from_bytes(self.message_binary)



# class Envelope(PicklableMixin):
#     """
#     An envelope is a convenience wrapper around a message's metadata (MessageMeta) and its
#     payload (MessageBase subclass).
#
#     This class provides API for
#         - MessageMeta creation, which includes payload signing, time stamping, and uuid generation
#         - signature verification
#         - payload deserialization
#
#     All ZMQ envelopes are formed with 3 frames:
#     1. Header -- a filter frame for Sub/Pub or an id frame for Dealer/Router. This is included as raw binary in a zmq
#                  frame, and is not wrapped in a capnp struct or any custom serialization format.
#     2. Metadata -- MessageMeta binary, which includes fields: type, uuid, signature, timestamp, and sender
#     3. Payload  -- a serialized MessageBase subclass, i.e. StandardTransaction or BlockContender
#
#     Note to self:
#     You want to create this class with an existing message meta instance, or without one by passing in keyword values
#     and such.
#     - It will be created from a messagebase instance when a new message created and sent
#     - It will be created from binary metadata and bytes when recv_multipart'd
#       from a zmq socket, and check the the message meta will be used for message duplication/sig validation, and
#     the
#     """
#
#     def __init__(self, raw_metadata: bytes=None, raw_data: bytes=None, metadata: MessageMeta=None,
#                  data: MessageMeta=None, validate=True):
#         assert raw_metadata or metadata, "Either a MessageMeta instance or metadata binary must be passed in"
#         assert raw_data or data, "Either a MessageBase instance or Metadata binary must be passed in"
#
#         self.log = get_logger("Envelope")
#         self._data = data
#         self._metadata = metadata
#         self._raw_data = raw_data
#         self._raw_metadata = raw_metadata
#
#         if validate:
#             self.validate()
#
#     def verify_signature(self, verifying_key: str):
#         return Constants.Protocols.Wallets.verify(verifying_key, self._raw_data, self.metadata.signature)
#
#     def validate(self):
#         a, b = None, None
#         try:
#             a = self.data
#             b = self.metadata
#         except Exception as e:
#             self.log.error("Error deserializing data and/or metadata: {}\ndata binary: {}\nmetadata binary: {}"
#                            .format(e, self._raw_data, self._raw_metadata))
#             return
#
#         a.validate()
#         b.validate()
#
#     @classmethod
#     def from_bytes(cls, payload: bytes, message_meta: bytes):
#         return cls(message_meta, payload)
#
#     @classmethod
#     def create(cls, signing_key: str, sender: str, data: MessageBase):
#         assert issubclass(type(data), MessageBase), "Data for envelope must be a MessageBase instance"
#         # TODO -- validate hex for sk and sender
#
#         data_binary = data.serialize()
#         payload_type = MessageBase.registry[type(data)]
#         signature = Constants.Protocol.Wallets.sign(signing_key, data_binary)
#         timestamp = time.time()
#
#         meta = MessageMeta.create(type=payload_type, signature=signature, sender=sender, timestamp=str(timestamp))
#         meta_binary = meta.serialize()
#         return cls(meta_binary, data_binary, validate=False)
#
#     @property
#     def data(self) -> MessageBase:
#         if not self._data:
#             self._data = MessageBase.registry[self.metadata.type].from_bytes(self._raw_data)
#
#         return self._data
#
#     @property
#     def metadata(self) -> MessageMeta:
#         if not self._metadata:
#             self._metadata = MessageMeta.from_bytes(self._raw_metadata)
#
#         return self._metadata
#
#     @property
#     def raw_data(self) -> bytes:
#         if not self._raw_data:
#             self._raw_data = self.data.serialize()
#
#         return self._raw_data
#
#     @property
#     def raw_metadata(self) -> bytes:
#         if not self._raw_metadata:
#             self._raw_metadata = self.metadata.serialize()
#
#         return self._raw_metadata






