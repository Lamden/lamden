import nacl
import nacl.encoding
import nacl.signing
from zmq.utils import z85
import secrets
from . import zbase


def verify(vk: str, msg: str, signature: str):
    vk = bytes.fromhex(vk)
    msg = msg.encode()
    signature = bytes.fromhex(signature)

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

    @property
    def signing_key(self):
        return self.sk.encode().hex()

    @property
    def verifying_key(self):
        return self.vk.encode().hex()

    def sign(self, msg: str):
        sig = self.sk.sign(msg.encode())
        return sig.signature.hex()

    @property
    def vk_pretty(self):
        key = zbase.bytes_to_zbase32(self.vk.encode())
        return 'pub_{}'.format(key[:-4])

    @property
    def sk_pretty(self):
        key = zbase.bytes_to_zbase32(self.sk.encode())
        return 'priv_{}'.format(key[:-4])
