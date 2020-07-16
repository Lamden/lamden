from unittest import TestCase
from lamden.crypto.wallet import Wallet, verify
from lamden.crypto.zbase import bytes_to_zbase32


class TestWallet(TestCase):
    def test_init_new_wallets(self):
        Wallet()

    def test_init_wallet_with_seed_returns_deterministic_wallet(self):
        w = Wallet()

        a = Wallet(seed=w.signing_key)

        self.assertEqual(w.vk, a.vk)
        self.assertEqual(w.sk, a.sk)

    def test_signing_key_as_str(self):
        w = Wallet()

        _w = w.signing_key

        self.assertTrue(isinstance(_w, str))

    def test_verifying_key_as_str(self):
        w = Wallet()

        _w = w.verifying_key

        self.assertTrue(isinstance(_w, str))

    def test_sign_bytes_returns_signature(self):
        w = Wallet()

        signature = w.sign('hello')

        self.assertTrue(isinstance(signature, str))
        self.assertEqual(len(signature), 128)

    def test_sign_bytes_returns_hex_signature(self):
        w = Wallet()

        signature = w.sign('hello')

        self.assertTrue(isinstance(signature, str))
        self.assertEqual(len(signature), 128)

    def test_signature_with_correct_message_returns_true(self):
        w = Wallet()

        message = 'howdy'
        signature = w.sign(message)

        self.assertTrue(verify(w.verifying_key, message, signature))

    def test_signature_with_wrong_message_returns_false(self):
        w = Wallet()

        message = 'howdy'
        signature = w.sign(message)

        self.assertFalse(verify(w.verifying_key, 'hello', signature))

    def test_signature_with_wrong_vk_returns_false(self):
        w = Wallet()

        message = 'howdy'
        signature = w.sign(message)

        a = Wallet()

        self.assertFalse(verify(a.verifying_key, message, signature))

    def test_pretty_vk_works(self):
        w = Wallet()

        b = 'pub_' + bytes_to_zbase32(bytes.fromhex(w.verifying_key))[:-4]

        self.assertEqual(w.vk_pretty, b)

    def test_pretty_sk_works(self):
        w = Wallet()

        b = 'priv_' + bytes_to_zbase32(bytes.fromhex(w.signing_key))[:-4]

        self.assertEqual(w.sk_pretty, b)