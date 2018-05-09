import nacl
import nacl.encoding
import nacl.signing

from cilantro.protocol.wallets import Wallet


class ED25519Wallet(Wallet):
    def __init__(self, s=None):
        if s is None:
            self.s, self.v = ED25519Wallet.new()
        else:
            self.s, self.v = ED25519Wallet.format_to_keys(s)
            self.s, self.v = ED25519Wallet.keys_to_format(self.s, self.v)

    @classmethod
    def generate_keys(cls, seed=None):
        if seed is not None:
            s = nacl.signing.SigningKey(seed=seed)
        else:
            s = nacl.signing.SigningKey.generate()
        v = s.verify_key
        return s, v

    @classmethod
    def get_vk(cls, s):
        s, v = ED25519Wallet.format_to_keys(s)
        s, v = ED25519Wallet.keys_to_format(s, v)
        return v

    @classmethod
    def keys_to_format(cls, s, v):
        s = s.encode()
        v = v.encode()
        return s.hex(), v.hex()

    @classmethod
    def format_to_keys(cls, s):
        s = bytes.fromhex(s)
        s = nacl.signing.SigningKey(s)
        return s, s.verify_key

    @classmethod
    def new(cls, seed=None):
        s, v = cls.generate_keys(seed=seed)
        return cls.keys_to_format(s, v)

    @classmethod
    def sign(cls, s, msg: bytes):
        assert type(msg).__name__ == 'bytes', 'Message argument must be a byte string.'
        (s, v) = cls.format_to_keys(s)
        return s.sign(msg).signature.hex()

    @classmethod
    def verify(cls, v, msg, sig):
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
