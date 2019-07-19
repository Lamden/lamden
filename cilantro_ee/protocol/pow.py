"""This is the basic SHA3 POW check implementation in cilantro_ee. It acts as a check on incoming transactions to act as an
anti-spam measure

Available classes:
-SHA3POW: This class implements find and check static methods which generate viable POW solutions"""


import hashlib
import secrets
# from cilantro_ee.constants.system_config import POW_COMPLEXITY

POW_COMPLEXITY = ''  # More '0's means more complicated POWs. Empty string basically disables POW


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


class DynamicPOW:
    @staticmethod
    def SHA3_512_1ST_HALF(data):
        h = hashlib.sha3_512()
        h.update(data)
        return h.digest()[:32]

    @staticmethod
    def SHA3_512_2ND_HALF(data):
        h = hashlib.sha3_512()
        h.update(data)
        return h.digest()[32:]

    @staticmethod
    def SHA3_256(data):
        h = hashlib.sha3_256()
        h.update(data)
        return h.digest()

    @staticmethod
    def SHA2_256(data):
        h = hashlib.sha256()
        h.update(data)
        return h.digest()

    @staticmethod
    def SHAKE_256_32_BYTES(data):
        h = hashlib.shake_256()
        h.update(data)
        return h.digest(32)

    @staticmethod
    def SHAKE_128_32_BYTES(data):
        h = hashlib.shake_128()
        h.update(data)
        return h.digest(32)

    @staticmethod
    def BLAKE2B_1ST_HALF(data):
        h = hashlib.blake2b()
        h.update(data)
        return h.digest()[:32]

    @staticmethod
    def BLAKE2B_2ND_HALF(data):
        h = hashlib.blake2b()
        h.update(data)
        return h.digest()[32:]

    ciphers = [
        SHA3_512_1ST_HALF,
        SHA3_512_2ND_HALF,
        SHA3_256,
        SHA2_256,
        SHAKE_256_32_BYTES,
        SHAKE_128_32_BYTES,
        BLAKE2B_1ST_HALF,
        BLAKE2B_2ND_HALF
    ]

    def pipeline_encryptor(self, state, nonce, step=4):
        data = nonce
        for i in range(len(state) // step):
            start = (i * step)
            end = (i * step) + step

            chunk = state[start:end]
            chunk_i = int(chunk.hex(), 16)
            selection = chunk_i % len(DynamicPOW.ciphers)

            cipher = DynamicPOW.ciphers[selection]

            data = cipher(data)

        return data

    DEFAULT_DIFF = '0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'

    def check_solution(self, state: bytes,
                       data: bytes,
                       nonce: bytes,
                       difficulty=DEFAULT_DIFF):
        d_i = int(difficulty, 16)

        h = hashlib.sha3_256()
        h.update(data)
        h.update(nonce)

        d = h.digest()

        work = self.pipeline_encryptor(state, d)
        w_i = int(work.hex(), 16)

        return w_i < d_i

    def find_solution(self, state: bytes, data: bytes):
        nonce = secrets.token_bytes(32)

        while not self.check_solution(state, data, nonce):
            nonce = secrets.token_bytes(32)

        return nonce