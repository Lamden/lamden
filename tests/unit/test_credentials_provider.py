import unittest

from lamden.sockets.router import CredentialsProvider
from lamden.crypto.wallet import Wallet

class TestCredentialsProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.credentials_provider: CredentialsProvider = None
        self.all_peers = []

    def tearDown(self) -> None:
        self.credentials_provider = None
        del self.credentials_provider

    def create_credentials_provider(self):
        self.credentials_provider = CredentialsProvider()
        for peer in self.all_peers:
            self.credentials_provider.add_key(vk=peer.local_vk)

    def get_all_peers(self):
        return self.all_peers

    def test_can_create_instance(self):
        self.create_credentials_provider()
        self.assertIsNotNone(self.credentials_provider)
        self.assertIsInstance(self.credentials_provider, CredentialsProvider)

    def test_METHOD_add_key__adds_key_to_approved_keys_dict(self):
        self.create_credentials_provider()

        wallet_1 = Wallet()
        vk = wallet_1.verifying_key

        self.credentials_provider.add_key(vk=vk)

        self.assertIsNotNone(self.credentials_provider.approved_keys.get(vk))
        self.assertEqual(wallet_1.curve_vk, self.credentials_provider.approved_keys.get(vk))

    def test_METHOD_add_key__raises_no_error_on_duplicate_key_add(self):
        self.create_credentials_provider()

        wallet_1 = Wallet()
        vk = wallet_1.verifying_key

        try:
            self.credentials_provider.add_key(vk=vk)
            self.credentials_provider.add_key(vk=vk)
        except Exception:
            self.fail("Should not raise errors when adding duplcate keys.")

    def test_METHOD_remove_key__removes_key_from_approved_keys_dict(self):
        self.create_credentials_provider()

        wallet_1 = Wallet()
        vk = wallet_1.verifying_key

        self.credentials_provider.add_key(vk=vk)
        self.assertIsNotNone(self.credentials_provider.approved_keys.get(vk))

        self.credentials_provider.remove_key(vk=vk)
        self.assertIsNone(self.credentials_provider.approved_keys.get(vk))

    def test_METHOD_remove_key__raises_no_error_if_key_doesnt_exist(self):
        self.create_credentials_provider()

        try:
            self.credentials_provider.remove_key(vk=Wallet().verifying_key)
        except Exception:
            self.fail("Should not raise errors when removing key that doesn't exist")

    def test_METHOD_key_is_approved__return_TRUE_if_key_in_approved_keys_dict(self):
        self.create_credentials_provider()

        wallet_1 = Wallet()
        vk = wallet_1.verifying_key

        self.credentials_provider.add_key(vk=vk)
        self.assertTrue(self.credentials_provider.key_is_approved(curve_vk=wallet_1.curve_vk))

    def test_METHOD_key_is_approved__return_FALSE_if_key_NOT_in_approved_keys_dict(self):
        self.create_credentials_provider()

        self.assertFalse(self.credentials_provider.key_is_approved(curve_vk=Wallet().curve_vk))

    def test_METHOD_callback__return_TRUE_if_key_in_approved_keys_dict(self):
        self.create_credentials_provider()

        wallet_1 = Wallet()
        vk = wallet_1.verifying_key

        self.credentials_provider.add_key(vk=vk)
        self.assertTrue(self.credentials_provider.callback(domain='', key=wallet_1.curve_vk))

    def test_METHOD_callback__return_FALSE_if_key_NOT_in_approved_keys_dict(self):
        self.create_credentials_provider()

        self.assertFalse(self.credentials_provider.callback(domain='', key=Wallet().curve_vk))

    def test_METHOD_callback__return_TRUE_if_always_approve_is_TRUE(self):
        self.create_credentials_provider()

        wallet_1 = Wallet()

        self.credentials_provider.accept_all = True

        self.assertTrue(self.credentials_provider.callback(domain='', key=wallet_1.curve_vk))

    def test_METHOD_open_messages__sets_approve_all_to_TRUE(self):
        self.create_credentials_provider()

        self.credentials_provider.accept_all = False
        self.credentials_provider.open_messages()

        self.assertTrue(self.credentials_provider.accept_all)

    def test_METHOD_secure_messages__sets_approve_all_to_FALSE(self):
        self.create_credentials_provider()

        self.credentials_provider.accept_all = True
        self.credentials_provider.secure_messages()

        self.assertFalse(self.credentials_provider.accept_all)




