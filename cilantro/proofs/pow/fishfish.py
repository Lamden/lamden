from cilantro.proofs.pow import POW
from twofish import Twofish
import pickle
import secrets

class TwofishPOW(POW):
    @classmethod
    def find(o):
        T = Twofish(o[0:32])
        x = secrets.token_bytes(16)
        secret = secrets.token_bytes(16)
        while x.hex()[0:3] != '000':
            secret = secrets.token_bytes(16)
            x = T.encrypt(secret)
        return secret.hex(), x.hex()

    @classmethod
    def check(o, proof):
        o = pickle.dumps(o)
        T = Twofish(o[0:32])
        x = T.encrypt(bytes.fromhex(proof))
        if x.hex()[0:3] == '000':
            return True
        return False