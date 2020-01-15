import nacl
import nacl.encoding
import nacl.signing
from zmq.utils import z85
import secrets
from . import zbase


def generate_keys(seed=None) -> tuple:
    if seed is not None:
        s = nacl.signing.SigningKey(seed=seed)
    else:
        s = nacl.signing.SigningKey.generate()
    v = s.verify_key
    return s, v


def get_vk(s) -> str:
    s, v = format_to_keys(s)
    s, v = keys_to_format(s, v)
    return v


def keys_to_format(s, v) -> tuple:
    s = s.encode()
    v = v.encode()
    return s.hex(), v.hex()


def format_to_keys(s) -> tuple:
    if type(s) != bytes:
        s = bytes.fromhex(s)
    s = nacl.signing.SigningKey(s)
    return s, s.verify_key


# Can be deprecated
def new(seed=None) -> tuple:
    s, v = generate_keys(seed=seed)
    return keys_to_format(s, v)


# Single instance in Merkle signature
def sign(s: str, msg: bytes) -> str:
    assert type(msg).__name__ == 'bytes', 'Message argument must be a byte string.'
    (s, v) = format_to_keys(s)
    return s.sign(msg).signature.hex()


# Single instance in Merkle Signature
def verify(v: str, msg: bytes, sig: str) -> bool:
    v = bytes.fromhex(v)
    sig = bytes.fromhex(sig)
    v = nacl.signing.VerifyKey(v)
    try:
        v.verify(msg, sig)
    except nacl.exceptions.BadSignatureError:
        return False
    except Exception:
        return False
    return True


def _sign(sk: bytes, msg: bytes):
    key = nacl.signing.SigningKey(seed=sk)
    sig = key.sign(msg)
    return sig.signature


def _verify(vk: bytes, msg: bytes, signature: bytes):
    vk = nacl.signing.VerifyKey(vk)
    try:
        vk.verify(msg, signature)
    except nacl.exceptions.BadSignatureError:
        return False
    return True


class Wallet:
    def __init__(self, seed=None):
        if isinstance(seed, str):
            seed = bytes.fromhex(seed)

        if seed is None:
            seed = secrets.token_bytes(32)

        self.sk = nacl.signing.SigningKey(seed=seed)
        self.vk = self.sk.verify_key

        self.curve_sk = z85.encode(self.sk.to_curve25519_private_key().encode())
        self.curve_vk = z85.encode(self.vk.to_curve25519_public_key().encode())

    @classmethod
    def from_sk(cls, sk):
        if type(sk) == str:
            sk = bytes.fromhex(sk)

        return Wallet(seed=sk)

    @staticmethod
    def format_key(k, as_hex=False):
        fk = k.encode()
        if as_hex:
            return fk.hex()
        return fk

    def signing_key(self, as_hex=False):
        return self.format_key(self.sk, as_hex=as_hex)

    def verifying_key(self, as_hex=False):
        return self.format_key(self.vk, as_hex=as_hex)

    def sign(self, msg: bytes, as_hex=False):
        assert isinstance(msg, bytes), 'Message must be byte string.'

        sig = self.sk.sign(msg)
        if as_hex:
            return sig.signature.hex()
        return sig.signature

    def verify(self, msg: bytes, signature: bytes):
        try:
            self.vk.verify(msg, signature)
        except nacl.exceptions.BadSignatureError:
            return False
        return True

    @property
    def vk_pretty(self):
        key = zbase.bytes_to_zbase32(self.vk.encode())
        return 'pub_{}'.format(key[:-4])

    @property
    def sk_pretty(self):
        key = zbase.bytes_to_zbase32(self.sk.encode())
        return 'priv_{}'.format(key[:-4])
