import ecdsa
from ecdsa import SigningKey, VerifyingKey, NIST192p
import hashlib
import base64

from cilantro.wallets import Wallet

class Base64Wallet(Wallet):
    def __init__(self, s=None):
        if s == None:
            self.s, self.v = Base64Wallet.new()
        else:
            self.s, self.v = Base64Wallet.format_to_keys(s)
            self.s, self.v = Base64Wallet.keys_to_format(self.s, self.v)

    @classmethod
    def generate_keys(cls):
        # generates a tuple keypair
        s = SigningKey.generate()
        v = s.get_verifying_key()
        return s, v

    @classmethod
    def keys_to_format(cls, s, v):
        # turns binary data into desired format
        s = s.to_string()
        v = v.to_string()
        return base64.b64encode(s), base64.b64encode(v)

    @classmethod
    def format_to_keys(cls, s):
        # returns the human readable format to bytes for processing
        s = base64.b64decode(s)

        # and into the library specific object
        s = SigningKey.from_string(s, curve=NIST192p)
        v = s.get_verifying_key()
        return s, v

    @classmethod
    def new(cls):
        # interface to creating a new wallet
        s, v = cls.generate_keys()
        return cls.keys_to_format(s, v)

    @classmethod
    def sign(cls, s, msg):
        (s, v) = cls.format_to_keys(s)
        signed_msg = s.sign(msg, hashfunc=hashlib.sha1, sigencode=ecdsa.util.sigencode_der)
        return base64.b64encode(signed_msg)

    @classmethod
    def verify(cls, v, msg, sig):
        v = base64.b64decode(v)
        v = VerifyingKey.from_string(v, curve=NIST192p)
        try:
            return v.verify(base64.b64decode(sig), msg, hashfunc=hashlib.sha1, sigdecode=ecdsa.util.sigdecode_der)
        except:
            return False