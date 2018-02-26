from cilantro.protocol.proofs import POW
import hashlib
import secrets

class SHA3POW(POW):
    @staticmethod
    def find(o: bytes):
        while True:
            h = hashlib.sha3_256()
            s = secrets.token_bytes(16)
            h.update(o + s)
            if h.digest().hex()[0:3] == '000':
                return s.hex(), h.digest().hex()

    @staticmethod
    def check(o: bytes, proof: str):
        h = hashlib.sha3_256()
        s = bytes.fromhex(proof)
        h.update(o + s)
        if h.digest().hex()[0:3] == '000':
            return True
        return False
