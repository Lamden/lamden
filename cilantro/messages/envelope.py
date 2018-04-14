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

    def __init__(self, raw_metadata: bytes=None, raw_data: bytes=None, metadata: MessageMeta=None,
                 data: MessageMeta=None, validate=True):
        assert raw_metadata or metadata, "Either a MessageMeta instance or metadata binary must be passed in"
        assert raw_data or data, "Either a MessageBase instance or Metadata binary must be passed in"

        self._data = data
        self._metadata = metadata
        self._raw_data = raw_data
        self._raw_metadata = raw_metadata

        if validate:
            self.validate()

    def verify_signature(self, verifying_key: str):
        return Constants.Protocols.Wallets.verify(verifying_key, self._raw_data, self.metadata.signature)

    def validate(self):
        a, b = None, None
        try:
            a = self.payload
            b = self.metadata
        except Exception as e:
            self.log.error("Error deserializing data and/or metadata: {}\ndata binary: {}\nmetadata binary: {}"
                           .format(e, self._raw_data, self._raw_metadata))
            return

        a.validate()
        b.validate()

    @classmethod
    def from_bytes(cls, payload: bytes, message_meta: bytes):
        return cls(message_meta, payload)

    @classmethod
    def create(cls, signing_key: str, sender: str, data: MessageBase):
        data_binary = data.serialize()
        payload_type = MessageBase.registry[type(data)]
        signature = Constants.Protocols.Wallets.sign(signing_key, data_binary)
        timestamp = time.time()

        meta = MessageMeta.create(type=payload_type, signature=signature, sender=sender, timestamp=str(timestamp))
        meta_binary = meta.serialize()
        return cls(meta_binary, data_binary, validate=False)

    @property
    def data(self) -> MessageBase:
        if not self._data:
            self._data = MessageBase.registry[self.metadata.type].from_bytes(self._raw_data)

        return self._data

    @property
    def metadata(self) -> MessageMeta:
        if not self._metadata:
            self._metadata = MessageMeta.from_bytes(self._raw_metadata)

        return self._metadata

    @property
    def raw_data(self) -> bytes:
        if not self._raw_data:
            self._raw_data = self.data.serialize()

        return self._raw_data

    @property
    def raw_metadata(self) -> bytes:
        if not self._raw_metadata:
            self._raw_metadata = self.metadata.serialize()

        return self._raw_metadata








