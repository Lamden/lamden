"""This is the basic SHA3 POW check implementation in cilantro. It acts as a check on incoming transactions to act as an
anti-spam measure

Available classes:
-SHA3POW: This class implements find and check static methods which generate viable POW solutions"""


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
        assert len(proof) == 32
        h = hashlib.sha3_256()
        s = bytes.fromhex(proof)
        h.update(o + s)
        if h.digest().hex()[0:3] == '000':
            return True
        return False
