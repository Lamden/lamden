from cilantro.protocol.serialization import JSONSerializer
from cilantro.protocol.proofs.pow import SHA3POW
from cilantro.protocol.wallets import ED25519
from cilantro.protocol.interpreters import vanilla as VanillaInterpreter

WALLET = ED25519
SERIALIZER = None
PROOF = SHA3POW
INTERPRETER = VanillaInterpreter


class TransactionBuilder:
    @classmethod
    def sign(cls, signing_key, data):
        return WALLET.sign(signing_key, data)

    @classmethod
    def seal(cls, data):
        return PROOF.find(data)

    @classmethod
    def build(cls, data):
        assert VanillaInterpreter.is_valid_transaction_type(data)
        [tx['type'] for tx in TX_TYPES]
        pass