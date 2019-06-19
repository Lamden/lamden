from cilantro_ee.storage.driver import SafeDriver
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.constants.masternode import NONCE_EXPIR
import secrets


class NonceManager:

    @classmethod
    def _user_nonce_key(cls, user_vk: str, nonce: str) -> str:
        return "{}:{}".format(user_vk, nonce)

    @classmethod
    def check_if_exists(cls, nonce: str) -> bool:
        return SafeDriver.exists(nonce)

    @classmethod
    def create_nonce(cls, user_vk: str) -> str:
        nonce = secrets.token_bytes(32).hex()
        key = cls._user_nonce_key(user_vk, nonce)

        # TODO this check if just for dev. remove it in prod.
        assert not cls.check_if_exists(key), "Nonce {} already exists!!!".format(key)

        SafeDriver.set(key, 1)
        SafeDriver.expire(key, NONCE_EXPIR)

        return key

    @classmethod
    def delete_nonce(cls, nonce: str):
        if cls.check_if_exists(nonce):
            SafeDriver.delete(nonce)


class NewNonceManager:
    def __init__(self):
        self.state = MetaDataStorage()

    def nonce_exists(self, s):
        return self.state.exists(s)

    def create_nonce(self, user_vk: str) -> str:
        nonce = secrets.token_bytes(32).hex()
        key = '{}:{}'.format(user_vk, nonce)

        # TODO this check if just for dev. remove it in prod.
        assert not self.check_if_exists(key), "Nonce {} already exists!!!".format(key)

        self.state.set(key, 1)
        #self.state.expire(key, NONCE_EXPIR)

        return key