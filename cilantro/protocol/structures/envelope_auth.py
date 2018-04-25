from cilantro import Constants
from cilantro.messages import MessageBase, Seal, MessageMeta


W = Constants.Protocol.Wallets


class EnvelopeAuth:

    @staticmethod
    def verify_seal(seal: Seal, meta: bytes, message: bytes) -> bool:
        """
        Verifies an envelope's seal, returning True if the signature is valid and False otherwise
        :param seal: The seal, as a Seal instance
        :param meta: The MessageMeta binary, as bytes
        :param message: The MessageBase binary, as a bytes
        :return: True if the seal's signature is valid; False otherwise
        """
        return W.verify(seal.verifying_key, meta + message, seal.signature)

    @staticmethod
    def seal(signing_key: str, meta, message) -> str:
        """
        Creates a signature for constructing a seal, as a function of the MessageMeta binary and MessageBase binary
        :param signing_key: The signing key as a hex string
        :param meta: The MessageMeta, as a MessageMeta instance or bytes (a serialized MessageMeta)
        :param message: The MessageBase, as a MessageBase instance or bytes (a serialized MessageBase)
        :return: The signed MessageMeta and MessageBase, as a 128 hex char long string
        """
        assert type(meta) in (MessageMeta, bytes), "meta arg must be a MessageMeta or bytes, not {}".format(type(meta))
        assert type(message) is bytes or issubclass(type(message), MessageBase), \
            "Message must be a MessageBase or bytes, not {}".format(type(message))
        # TODO -- verify singing_key valid length hex

        if type(meta) is not bytes:
            meta = meta.serialize()
        if type(message) is not bytes:
            message = message.serialize()

        return W.sign(signing_key, meta + message)
