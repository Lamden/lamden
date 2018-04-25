from cilantro.messages import MessageBase
import capnp
import envelope_capnp


class Seal(MessageBase):
    @classmethod
    def _deserialize_data(cls, data: bytes):
        return envelope_capnp.Seal.from_bytes_packed(data)

    def validate(self):
        # TODO -- ensure self.signature and self.verifying_key are of valid form (hex, 64/128 chars)
        pass

    @classmethod
    def create(cls, signature: str, verifying_key: str):
        data = envelope_capnp.Seal.new_message()
        data.signature = signature
        data.verifyingKey = verifying_key

        return cls.from_data(data)

    @property
    def signature(self):
        return self._data.signature.decode()

    @property
    def verifying_key(self):
        return self._data.verifyingKey.decode()

