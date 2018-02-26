from cilantro.protocol.serialization import JSONSerializer
from cilantro.protocol.proofs.pow import SHA3POW
from cilantro.protocol.wallets import ED25519

SERIALIZER = JSONSerializer
PROOF = SHA3POW
WALLET = ED25519
INTERPRETER = None

JSON = {
    'payload': None,
    'proof': None,
    'signature': None
}


def serialize(data):
    return data


def deserialize(data):
    return data


def from_json(data):
    pass


def new():
    return {
        'payload': None,
        'proof': None,
        'signature': None
    }

def is_valid(data):
    pass