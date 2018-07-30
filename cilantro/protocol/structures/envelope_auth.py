from cilantro.utils import Hasher

from cilantro.messages.envelope.seal import Seal
from cilantro.messages.envelope.message_meta import MessageMeta
from cilantro.messages.base.base import MessageBase

import math
from cilantro.constants.protocol import max_uuid

"""
TODO investigate why below is setting var 'W' to the string 'ED25519Wallet' instead of the actual object (as of 5/21)
appears that this is the only place that happens. Must have something to do with order of imports, and Constants
not being 'built' properly by the time this is accessed
"""

from cilantro.protocol.wallet import Wallet
W = Wallet  # hack until we fix above

UUID_SIZE = int(math.log2(max_uuid))  # size of UUID field on messagemeta struct as number of bits


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

    @staticmethod
    def reply_uuid(request_uuid: int):
        """
        Returns the associated reply UUID for some request UUID. This is simply the SHA3 256 hash of the request's UUID.
        :param request_uuid: The request UUID to generate a reply UUID for
        :return: An int, denoting the reply UUID associated with the passed in request UUID
        """
        int_binary = Hasher.hash(request_uuid, algorithm=Hasher.Alg.SHAKE_128, digest_len=UUID_SIZE//8, return_bytes=True)
        rep_uuid = int.from_bytes(int_binary, byteorder='little')  # capnp int fields encoded in little endian

        # This assertion is for debugging only. Remove for production.
        assert rep_uuid <= max_uuid, "OH NO! Got reply uuid greater than MaxUUID! LOGIC ERROR!!!"

        return rep_uuid

