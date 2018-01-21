from unittest import TestCase
from cilantro.wallets import Base64Wallet

class TestBase64Wallet(TestCase):

    def test_key_from_string(self):
        pass

    def test_sign_and_verify(self):
        (s, v) = Base64Wallet.new()
        (s2, v2) = Base64Wallet.new()

        msg = b'hello there'
        sig = Base64Wallet.sign(s, msg)

        self.assertTrue(Base64Wallet.verify(v, msg, sig))
        self.assertFalse(Base64Wallet.verify(v2, msg, sig))