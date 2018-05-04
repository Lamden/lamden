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
    def create_from_message(cls, message: MessageBase, signing_key: str, verifying_key: str=None, uuid: int=-1):
        assert issubclass(type(message), MessageBase), "message arg must be a MessageBase subclass"
        assert type(message) in MessageBase.registry, "Message type {} not found in registry {}"\
            .format(type(message), MessageBase.registry)
        # TODO -- verify sk (valid hex, 128 char)

        # TODO get rid of sender_id, fuck that shit, we got the VK on the seal and that shoudl be all we need

        # TODO add either another factory method, or add a default uuid arg to this func so we can create message meta
        # with a predetermined uuid (this is for creatnig reply envelopes)

        # Create MessageMeta
        t = MessageBase.registry[type(message)]
        timestamp = str(time.time())
        meta = MessageMeta.create(type=t, timestamp=timestamp, uuid=uuid)

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
        # Try to access .seal/.meta./.message to make sure they deserialize properly
        # assert type(self._data) == capnp.lib.capnp._DynamicStructBuilder, "envelopes's _data must be a capnp struct"\
        #    .format(self._data)
        # assert self.seal in self._data, "seal missing from data {}".format(self._data)
        # assert self.meta in self._data, "meta field missing from data {}".format(self._data)
        # assert self.message in self._data, "message missing from data {}".format(self._data)
        pass
        # TODO verify

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




