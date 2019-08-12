import hashlib
import secrets

DEFAULT_DIFF = '0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'


def SHA3_512_1ST_HALF(data):
    h = hashlib.sha3_512()
    h.update(data)
    return h.digest()[:32]


def SHA3_512_2ND_HALF(data):
    h = hashlib.sha3_512()
    h.update(data)
    return h.digest()[32:]


def SHA3_256(data):
    h = hashlib.sha3_256()
    h.update(data)
    return h.digest()


def SHA2_256(data):
    h = hashlib.sha256()
    h.update(data)
    return h.digest()


def SHAKE_256_32_BYTES(data):
    h = hashlib.shake_256()
    h.update(data)
    return h.digest(32)


def SHAKE_128_32_BYTES(data):
    h = hashlib.shake_128()
    h.update(data)
    return h.digest(32)


def BLAKE2B_1ST_HALF(data):
    h = hashlib.blake2b()
    h.update(data)
    return h.digest()[:32]


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


def encrypt(state, nonce, step=4):
    data = nonce
    for i in range(len(state) // step):
        start = (i * step)
        end = (i * step) + step

        chunk = state[start:end]
        chunk_i = int(chunk.hex(), 16)
        selection = chunk_i % len(ciphers)

        cipher = ciphers[selection]

        data = cipher(data)

    return data


def check_solution(state: bytes,
                   data: bytes,
                   nonce: bytes,
                   difficulty=DEFAULT_DIFF):

    if len(nonce) != 32:
        return False

    d_i = int(difficulty, 16)

    h = hashlib.sha3_256()
    h.update(data+nonce)

    d = h.digest()

    solution = encrypt(state, d)
    s_i = int(solution.hex(), 16)

    return s_i < d_i


def find_solution(state: bytes, data: bytes, difficulty=DEFAULT_DIFF):
    nonce = secrets.token_bytes(32)

    while not check_solution(state, data, nonce, difficulty=difficulty):
        nonce = secrets.token_bytes(32)

    return nonce