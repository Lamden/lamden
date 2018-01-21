from twofish import Twofish
import pickle
import secrets
from transactions import transaction
from wallets import basic_wallet as wallet

from transactions import TransactionType

class BasicTransaction(TransactionType):
    def __init__(self, wallet):
        self.wallet = wallet

    def payload(*args):
        return {
            'to': args[0],
            'from': args[1],
            'amount': args[2]
        }

    @staticmethod
    def metadata(payload, s):
        payload = pickle.dumps(payload)
        return {
            'signature': wallet.sign(s, payload),
            'proof': find_nonce(payload)[0]
        }

    @staticmethod
    def build(**kwargs):
        to = kwargs['to']
        v = kwargs['v']
        amount = kwargs['amount']
        s = kwargs['s']

        p = payload(to, v, amount)
        m = metadata(p, s)
        return {
            'payload': p,
            'metadata': m
        }

    @staticmethod
    def find_nonce(o):
        T = Twofish(o[0:32])
        x = secrets.token_bytes(16)
        secret = secrets.token_bytes(16)
        while x.hex()[0:3] != '000':
            secret = secrets.token_bytes(16)
            x = T.encrypt(secret)

        return secret.hex(), x.hex()

    @staticmethod
    def check_proof(o, proof):
        o = pickle.dumps(o)
        T = Twofish(o[0:32])
        x = T.encrypt(bytes.fromhex(proof))
        if x.hex()[0:3] == '000':
            return True
        return False


def payload(*args):
    return {
        'to' : args[0],
        'from' : args[1],
        'amount' : args[2]
    }
def metadata(payload, s):
    payload = pickle.dumps(payload)
    return {
        'signature' : wallet.sign(s, payload),
        'proof' : find_nonce(payload)[0]
    }
def build(**kwargs):
    to = kwargs['to']
    v = kwargs['v']
    amount = kwargs['amount']
    s = kwargs['s']

    p = payload(to, v, amount)
    m = metadata(p, s)
    return {
        'payload' : p,
        'metadata' : m
    }
def find_nonce(o):
    T = Twofish(o[0:32])
    x = secrets.token_bytes(16)
    secret = secrets.token_bytes(16)
    while x.hex()[0:3] != '000':
        secret = secrets.token_bytes(16)
        x = T.encrypt(secret)

    return secret.hex(), x.hex()
def check_proof(o, proof):
    o = pickle.dumps(o)
    T = Twofish(o[0:32])
    x = T.encrypt(bytes.fromhex(proof))
    if x.hex()[0:3] == '000':
        return True
    return False