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


class Serializer:
    def __init__(self, capnp_type, sign=True, prove=True):
        self.capnp_type = capnp_type
        self.sign = sign
        self.prove = prove

    def unpack(self, msg):
        message = envelope_capnp.Message.from_bytes_packed(msg)
        if (self.sign and not _verify(msg.verifying_key, msg.payload, msg.signature)) or \
                (self.prove and not SHA3POW.check(msg.payload, msg.proof)):
                return None

        final_message = self.capnp_type.from_bytes_packed(message.payload)
        return final_message

    def pack(self, msg, wallet=None):
        message = envelope_capnp.Message.new_message(payload=msg)

        if self.sign:
            if wallet is None:
                return None
            message.verifying_key = wallet.verifying_key()
            message.signature = wallet.sign(message.payload)

        if self.prove:
            message.proof = SHA3POW.find(message.payload)

        return message

TYPE_MAP = {
    20000: Serializer(capnp_type=transaction_capnp.ContractTransaction, sign=True, prove=True),
    30000: Serializer(capnp_type=transaction_capnp.ContractTransaction, sign=True, prove=True)
}

