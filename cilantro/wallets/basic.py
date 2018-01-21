from ecdsa import SigningKey, VerifyingKey, NIST192p
import ecdsa
import hashlib

from cilantro.wallets import Wallet

class BasicWallet(Wallet):
    def __init__(self, s=None):
        if s == None:
            self.s, self.v = BasicWallet.new()
        else:
            self.s, self.v = BasicWallet.format_to_keys(s)
            self.s, self.v = BasicWallet.keys_to_format(self.s, self.v)

    @staticmethod
    def generate_keys():
        # generates a tuple keypair
        s = SigningKey.generate()
        v = s.get_verifying_key()
        return s, v

    @staticmethod
    def keys_to_format(s, v):
        # turns binary data into desired format
        s = s.to_string()
        v = v.to_string()
        return s.hex(), v.hex()

    @staticmethod
    def format_to_keys(s):
        # returns the human readable format to bytes for processing
        s = bytes.fromhex(s)

        # and into the library specific object
        s = SigningKey.from_string(s, curve=NIST192p)
        v = s.get_verifying_key()
        return s, v

    @staticmethod
    def new():
        # interface to creating a new wallet
        s, v = generate_keys()
        return keys_to_format(s, v)


    @staticmethod
    def sign(s, msg):
        (s, v) = format_to_keys(s)
        signed_msg = s.sign(msg, hashfunc=hashlib.sha1, sigencode=ecdsa.util.sigencode_der)
        return signed_msg.hex()

    @staticmethod
    def verify(v, msg, sig):
        v = bytes.fromhex(v)
        v = VerifyingKey.from_string(v, curve=NIST192p)
        try:
            return v.verify(bytes.fromhex(sig), msg, hashfunc=hashlib.sha1, sigdecode=ecdsa.util.sigdecode_der)
        except:
            return False