from cilantro_ee.storage.ledis import SafeLedis
from cilantro_ee.constants.masternode import NONCE_EXPIR
import secrets


class NonceManager:

    @classmethod
    def _user_nonce_key(cls, user_vk: str, nonce: str) -> str:
        return "{}:{}".format(user_vk, nonce)

    @classmethod
    def check_if_exists(cls, nonce: str) -> bool:
        return SafeLedis.exists(nonce)

    @classmethod
    def create_nonce(cls, user_vk: str) -> str:
        nonce = secrets.token_bytes(32).hex()
        key = cls._user_nonce_key(user_vk, nonce)

        # TODO this check if just for dev. remove it in prod.
        assert not cls.check_if_exists(key), "Nonce {} already exists!!!".format(key)

        SafeLedis.set(key, 1)
        SafeLedis.expire(key, NONCE_EXPIR)

        return key

    @classmethod
    def delete_nonce(cls, nonce: str):
        if cls.check_if_exists(nonce):
            SafeLedis.delete(nonce)
