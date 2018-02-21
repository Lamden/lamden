import nacl
import nacl.encoding
import nacl.signing

import ed25519

from cilantro.wallets import Wallet

class ED25519Wallet(Wallet):
    def __init__(self, s=None):
        if s == None:
            self.s, self.v = ED25519Wallet.new()
        else:
            self.s, self.v = ED25519Wallet.format_to_keys(s)
            self.s, self.v = ED25519Wallet.keys_to_format(self.s, self.v)

    @classmethod
    def generate_keys(cls):
        return ed25519.create_keypair()

    @classmethod
    def keys_to_format(cls, s, v):
        s = s.to_bytes()
        v = v.to_bytes()
        return s.hex(), v.hex()

    @classmethod
    def format_to_keys(cls, s):
        s = bytes.fromhex(s)
        s = ed25519.SigningKey(s)
        return s, s.get_verifying_key()

    @classmethod
    def new(cls):
        s, v = cls.generate_keys()
        return cls.keys_to_format(s, v)

    @classmethod
    def sign(cls, s, msg: bytes):
        assert type(msg).__name__ == 'bytes', 'Message argument must be a byte string.'
        (s, v) = cls.format_to_keys(s)
        return s.sign(msg).hex()

    @classmethod
    def verify(cls, v, msg, sig):
        v = bytes.fromhex(v)
        sig = bytes.fromhex(sig)
        v = ed25519.VerifyingKey(v)
        try:
            v.verify(sig, msg)
        except:
            return False
        return True