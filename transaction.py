from twofish import Twofish
import pickle
import secrets

# returns the serialization data 'for the wire'
def new(payload, signature, proof):
    return 0

def find_nonce(o):
    T = Twofish(o[0:32])
    x = secrets.token_bytes(16)
    secret = secrets.token_bytes(16)
    while x.hex()[0:3] != '000':
        secret = secrets.token_bytes(16)
        x = T.encrypt(secret)

    return secret.hex(), x.hex()