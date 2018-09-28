from cilantro.protocol import wallet
from os.path import basename, splitext, join, exists
from zmq.auth.thread import ThreadAuthenticator
from zmq.auth.asyncio import AsyncioAuthenticator
from zmq.utils.z85 import decode, encode
from nacl.public import PrivateKey, PublicKey
from nacl.signing import SigningKey, VerifyKey
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519
from cilantro.storage.db import VKBook
from cilantro.logger import get_logger
from cilantro.utils import lazy_property

class Auth:

    @classmethod
    def set_keys(cls, sk_hex):
        cls.sk = sk_hex
        cls.vk = cls._sk.verify_key.encode().hex()

    @classmethod
    def vk2pk(cls, vk):
        return encode(VerifyKey(bytes.fromhex(vk)).to_curve25519_public_key()._public_key)

    @lazy_property
    def public_key(self):
        return self.vk2pk(cls.vk)

    @lazy_property
    def private_key(self):
        return crypto_sign_ed25519_sk_to_curve25519(cls.sk._signing_key).hex()

    @classmethod
    def generate_certificates():
        sk = SigningKey(seed=bytes.fromhex(cls.sk))
        vk = cls.vk
        public_key = cls.vk2pk(vk)
        keyname = decode(public_key).hex()
        private_key = crypto_sign_ed25519_sk_to_curve25519(sk._signing_key).hex()
        authorized_keys_dir = custom_folder or cls.authorized_keys_dir
        for d in [cls.keys_dir, authorized_keys_dir]:
            if exists(d):
                shutil.rmtree(d)
            os.makedirs(d, exist_ok=True)

        secret = None

        _, secret = cls.create_from_private_key(private_key, keyname)

        for key_file in os.listdir(cls.keys_dir):
            if key_file.endswith(".key"):
                shutil.move(join(cls.keys_dir, key_file),
                            join(authorized_keys_dir, '.'))

        if exists(cls.keys_dir):
            shutil.rmtree(cls.keys_dir)

        log.info('Generated CURVE certificate files!')

        return vk, public_key, secret
