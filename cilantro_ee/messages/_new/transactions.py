import secrets
import transaction_capnp

# sender @0 :Text;
#     nonce @1 :Text;
#     stampsSupplied @2 :UInt64;
#
#     contractName @3 :Text;
#     functionName @4 :Text;
#     kwargs @5 :V.Map(Text, V.Value);
#

class Message:
    def serialize(self):
        raise NotImplementedError

# Certain messages can be signed.
class SignableMessage(Message):
    def sign(self):
        raise NotImplementedError


class ContractTransaction(SignableMessage):
    def __init__(self, sender: bytes, nonce: bytes, stamps: int, contract: str, function: str, kwargs: dict):
        assert len(sender) == 32, 'Sender VK must be 32 bytes.'

        self.sender = sender
        if nonce == None:
            self.nonce = secrets.token_bytes(64)

        assert len(nonce) == 64, 'Nonce must be 64 bytes.'

        self.stamps = stamps
        self.contract = contract
        self.function = function
        self.kwargs = kwargs

        self.ready = False

    def serialize(self):
        if self.ready:
            pass
        return None