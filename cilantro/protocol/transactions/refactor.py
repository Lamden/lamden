from cilantro.protocol.serialization import JSONSerializer
from cilantro.protocol.proofs.pow import SHA3POW
from cilantro.protocol.wallets import ED25519

SERIALIZER = JSONSerializer
PROOF = SHA3POW
WALLET = ED25519

JSON = {
    'payload': None,
    'proof': None,
    'signature': None
}


def sign(data):
    return WALLET.sign()


def seal(data):
    return data


def serialize(data):
    return data


def from_json(data):
    pass


class Transaction(object):
    def __init__(self, payload_data):
        self.payload = payload_data
        self.proof = None
        self.signature = None