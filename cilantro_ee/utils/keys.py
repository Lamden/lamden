from zmq.utils.z85 import encode
from nacl.signing import SigningKey, VerifyKey
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519
import hashlib


class Keys:
    is_setup = False

    @classmethod
    def setup(cls, sk_hex):
        if not cls.is_setup:
            nacl_sk = SigningKey(seed=bytes.fromhex(sk_hex))
            cls.sk = sk_hex
            cls.vk = nacl_sk.verify_key.encode().hex()

            # DEBUG -- TODO DELETE
            from cilantro_ee.core.crypto.wallet import get_vk
            wall_vk = get_vk(cls.sk)
            assert wall_vk == cls.vk, "wallet vk {} not match nacl vk {}".format(wall_vk, cls.vk)
            # END DEBUG

            cls.public_key = cls.vk2pk(cls.vk)
            cls.private_key = crypto_sign_ed25519_sk_to_curve25519(nacl_sk._signing_key)
            cls.is_setup = True

    #TODO replace with Wallet class that has the same functionality
    @staticmethod
    def vk2pk(vk):
        return encode(VerifyKey(bytes.fromhex(vk)).to_curve25519_public_key()._public_key)

    #TODO Deprecate
    @staticmethod
    def digest(s):
        if not isinstance(s, bytes):
            s = str(s).encode('utf8')
        return hashlib.sha1(s).digest()

