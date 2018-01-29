from cilantro.proofs.pow import POW
from twofish import Twofish
import secrets

class TwofishPOW(POW):
    @staticmethod
    def find(o: bytes):
        T = Twofish(o[0:32])
        x = secrets.token_bytes(16)
        secret = secrets.token_bytes(16)
        while x.hex()[0:3] != '000':
            secret = secrets.token_bytes(16)
            x = T.encrypt(secret)
        return secret.hex(), x.hex()

    @staticmethod
    def check(o: bytes, proof: str):
        T = Twofish(o[0:32])
        x = T.encrypt(bytes.fromhex(proof))
        if x.hex()[0:3] == '000':
            return True
        return False