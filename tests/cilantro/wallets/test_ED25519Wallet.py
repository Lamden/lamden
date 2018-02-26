from unittest import TestCase
from cilantro.protocol.wallets import ED25519Wallet

class TestED25519Wallet(TestCase):

    def test_key_from_string(self):
        pass

    def test_sign_and_verify(self):
        (s, v) = ED25519Wallet.new()
        (s2, v2) = ED25519Wallet.new()

        msg = b'hello there'
        sig = ED25519Wallet.sign(s, msg)

        self.assertTrue(ED25519Wallet.verify(v, msg, sig))
        self.assertFalse(ED25519Wallet.verify(v2, msg, sig))