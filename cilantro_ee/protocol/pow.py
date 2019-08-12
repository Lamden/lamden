"""This is the basic SHA3 POW check implementation in cilantro_ee. It acts as a check on incoming transactions to act as an
anti-spam measure

Available classes:
-SHA3POW: This class implements find and check static methods which generate viable POW solutions"""


import hashlib
import secrets
# from cilantro_ee.constants.system_config import POW_COMPLEXITY

POW_COMPLEXITY = ''  # More '0's means more complicated POWs. Empty string basically disables POW
POW_BYTES_DIFFICULTY = (2 ** 256) - (2 ** 255) # REALLY SIMPLE PROOF

class SHA3POW:
    @staticmethod
    def find(o: bytes):
        while True:
            h = hashlib.sha3_256()
            s = secrets.token_bytes(16)
            h.update(o + s)
            if h.digest().hex()[0:len(POW_COMPLEXITY)] == POW_COMPLEXITY:
                return s.hex(), h.digest().hex()

    @staticmethod
    def check(o: bytes, proof: str):
        assert len(proof) == 32
        h = hashlib.sha3_256()
        s = bytes.fromhex(proof)
        h.update(o + s)
        return h.digest().hex()[0:len(POW_COMPLEXITY)] == POW_COMPLEXITY


class SHA3POWBytes:
    @staticmethod
    def find(o: bytes):
        while True:
            h = hashlib.sha3_256()
            s = secrets.token_bytes(16)
            h.update(o + s)
            if int(h.digest().hex(), 16) < POW_BYTES_DIFFICULTY:
                return s

    @staticmethod
    def check(o: bytes, proof: bytes):
        if not len(proof) == 16:
            return False
        h = hashlib.sha3_256()
        h.update(o + proof)
        return int(h.digest().hex(), 16) < POW_BYTES_DIFFICULTY
