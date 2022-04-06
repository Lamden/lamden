import unittest
import asyncio

from lamden.sockets.router import Router, CredentialsProvider
from lamden.crypto.wallet import Wallet

class TestRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.router_wallet = Wallet()

    def setUp(self) -> None:
        self.wallet = self.__class__.router_wallet
        self.router = None
        self.all_peers = []

    def tearDown(self) -> None:
        pass

    def create_router(self):
        self.router = Router(
            router_wallet=self.router_wallet,
            get_all_peers=self.get_all_peers
        )

    def get_all_peers(self):
        return self.all_peers

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_instance(self):
        self.create_router()
        self.assertIsNotNone(self.router)

    def test_can_create_instance(self):
        self.create_router()
        self.assertIsNotNone(self.router)
        self.assertIsInstance(self.router, Router)

    def test_creates_credientials_provider_instnace(self):
        self.create_router()
        self.assertIsNotNone(self.router.cred_provider)
        self.assertIsInstance(self.router.cred_provider, CredentialsProvider)


