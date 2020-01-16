from unittest import TestCase
from cilantro_ee.crypto.wallet import Wallet


class TestWallet(TestCase):
    def test_init_new_wallets(self):
        Wallet()

    def test_init_wallet_with_seed_returns_deterministic_wallet(self):
        w = Wallet()

        a = Wallet(seed=w.signing_key())

        self.assertEqual(w.vk, a.vk)
        self.assertEqual(w.sk, a.sk)

    def test_signing_key_as_bytes(self):
        w = Wallet()

        _w = w.signing_key()

        self.assertTrue(isinstance(_w, bytes))

        _h = w.signing_key(as_hex=True)

        self.assertTrue(isinstance(_h, str))

    def test_verifying_key_as_bytes(self):
        w = Wallet()

        _w = w.verifying_key()

        self.assertTrue(isinstance(_w, bytes))

        _h = w.verifying_key(as_hex=True)

        self.assertTrue(isinstance(_h, str))

    def test_sign_string_breaks(self):
        w = Wallet()

        with self.assertRaises(AssertionError):
            w.sign('hello')

    def test_sign_bytes_returns_signature(self):
        w = Wallet()

        signature = w.sign(b'hello')

        self.assertTrue(isinstance(signature, bytes))
        self.assertEqual(len(signature), 64)

    def test_sign_bytes_returns_hex_signature(self):
        w = Wallet()

        signature = w.sign(b'hello', as_hex=True)

        self.assertTrue(isinstance(signature, str))
        self.assertEqual(len(signature), 128)

    def test_signature_with_correct_message_returns_true(self):
        w = Wallet()

        message = b'howdy'
        signature = w.sign(message)

        self.assertTrue(w.verify(message, signature))

    def test_signature_with_wrong_message_returns_false(self):
        w = Wallet()

        message = b'howdy'
        signature = w.sign(message)

        self.assertFalse(w.verify(b'hello', signature))

    def test_signature_with_wrong_vk_returns_false(self):
        w = Wallet()

        message = b'howdy'
        signature = w.sign(message)

        a = Wallet()

        self.assertFalse(a.verify(message, signature))
