import capnp
from cilantro_ee.protocol.wallet import Wallet, _verify
from cilantro_ee.protocol.pow import SHA3POW

blockdata_capnp = capnp.load('../capnp/blockdata.capnp')
subblock_capnp = capnp.load('../capnp/subblock.capnp')
envelope_capnp = capnp.load('../capnp/envelope.capnp')
transaction_capnp = capnp.load('../capnp/transaction.capnp')

# Message type registration
# Each type is a uint32 number (0 - 4294967295)
#     0 -  9999 = block data
# 10000 - 19999 = envelope
# 20000 - 29999 = transaction
# 30000 - 39999 = signals
# 40000 - 49999 = consensus

# Type -> (envelope, capnp_deserializer)


class Unpacker:
    @staticmethod
    def unpack(msg, deserializer):
        message = envelope_capnp.Message.from_bytes_packed(msg)
        final_message = deserializer.from_bytes_packed(message.payload)
        return final_message


class VerifiedUnpacker:
    @staticmethod
    def unpack(msg, deserializer):
        message = envelope_capnp.VerifiedMessage.from_bytes_packed(msg)
        if _verify(message.verifying_key, message.payload, message.signature):
            final_message = deserializer.from_bytes_packed(message.payload)
            return final_message
        return None


class ProvenVerifiedUnpacker:
    @staticmethod
    def unpack(msg, deserializer):
        message = envelope_capnp.VerifiedMessage.from_bytes_packed(msg)
        if _verify(message.verifying_key, message.payload, message.signature) and \
                SHA3POW.check(message.payload, message.proof):

            final_message = deserializer.from_bytes_packed(message.payload)
            return final_message
        return None


TYPE_MAP = {
    30000: (Unpacker, None)
}


def deserialize(msg_type, msg):
    unpacker, deserializer = TYPE_MAP.get(msg_type)
    if deserializer is None:
        return None

    return unpacker.unpack(msg, deserializer)
