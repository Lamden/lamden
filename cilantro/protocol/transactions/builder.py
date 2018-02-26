from cilantro.protocol.serialization import JSONSerializer
from cilantro.protocol.proofs.pow import SHA3POW
from cilantro.protocol.wallets import ED25519

WALLET = ED25519
SERIALIZER = None
PROOF = SHA3POW

VOTE = {'type': 'v', 'sender': None, 'key': None, 'value': None}
STD = {'type': 'v', 'sender': None, 'reciever': None, 'amount': None}
SWAP = {'type': 'swap', 'sender': None, 'amount': None, 'hash_lock': None, 'unix_expiration': None}
REDEEM = {'type': 'r', 'sender': None, 'secret': None}
STAMP = {'type': 'stamp', 'sender': None, 'amount': None}

TX_TYPES = [VOTE, STD, SWAP, REDEEM, STAMP]

class TransactionBuilder:
    @classmethod
    def sign(cls, signing_key, data):
        return WALLET.sign(signing_key, data)

    @classmethod
    def seal(cls, data):
        return PROOF.find(data)

    @classmethod
    def build(cls, data):
        # interpreter here?
        [tx['type'] for tx in TX_TYPES]
        pass