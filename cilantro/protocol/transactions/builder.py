from .constants import *


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
        pass
