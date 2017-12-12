from twofish import Twofish
import pickle
import secrets

class Transaction():
    def __init__(t, f, a):
        self.data = {
            'to' : t,
            'from' : f,
            'amount' : a
        }

def find_nonce(o):
    T = Twofish(pickle.dumps(o)[0:32])
    x = secrets.token_bytes(16)
    secret = secrets.token_bytes(16)
    while x.hex()[0:3] != '000':
        secret = secrets.token_bytes(16)
        x = T.encrypt(secret)

    return secret.hex(), x.hex()