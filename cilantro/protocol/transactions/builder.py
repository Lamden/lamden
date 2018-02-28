from cilantro import Constants

class TransactionBuilder:
    @classmethod
    def sign(cls, signing_key, data):
        return Constants.Protocol.Wallets.sign(signing_key, data)

    @classmethod
    def seal(cls, data):
        return Constants.Protocol.Proofs.find(data)

    @classmethod
    def build(cls, data):
        assert Constants.Protocol.Interpreters.is_valid_transaction_type(data)
        pass
