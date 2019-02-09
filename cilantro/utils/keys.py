from zmq.utils.z85 import decode, encode
from nacl.public import PrivateKey, PublicKey
from nacl.signing import SigningKey, VerifyKey
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519, crypto_sign_ed25519_pk_to_curve25519
from nacl.encoding import HexEncoder

class Keys:
    is_setup = False
    @classmethod
    def setup(cls, sk_hex):
        if not cls.is_setup:
            nacl_sk = SigningKey(seed=bytes.fromhex(sk_hex))
            cls.sk = sk_hex
            cls.vk = nacl_sk.verify_key.encode().hex()
            cls.public_key = cls.vk2pk(cls.vk)
            cls.private_key = crypto_sign_ed25519_sk_to_curve25519(nacl_sk._signing_key)
            cls.is_setup = True

    # @classmethod
    # def get_keys(cls, sk_hex):
    #     sk = SigningKey(seed=bytes.fromhex(sk_hex))
    #     vk = sk.verify_key.encode().hex()
    #     public_key = cls.vk2pk(vk)
    #     private_key = crypto_sign_ed25519_sk_to_curve25519(sk._signing_key)
    #     return sk, vk, public_key, private_key
    # @classmethod
    # def sign(cls, msg):
    #     return cls._sk.sign(msg)
    #
    # @classmethod
    # def verify(cls, vk, msg, sig):
    #     return VerifyKey(vk, encoder=HexEncoder).verify(msg, sig)

    @staticmethod
    def vk2pk(vk):
        return encode(VerifyKey(bytes.fromhex(vk)).to_curve25519_public_key()._public_key)
