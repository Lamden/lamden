import unittest
from unittest import TestCase
from os import listdir, makedirs
from os.path import exists, join
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519
from cilantro.utils.keys import Keys
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
from nacl.signing import SigningKey

class TestKeys(TestCase):
    def test_setup(self):
        sk, vk = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']
        Keys.setup(sk)
        self.assertEqual(Keys.sk, sk)
        self.assertEqual(Keys.vk, vk)
        self.assertEqual(Keys.public_key, Keys.vk2pk(vk))
        self.assertEqual(Keys.private_key, crypto_sign_ed25519_sk_to_curve25519(SigningKey(seed=bytes.fromhex(sk))._signing_key))

if __name__ == '__main__':
    unittest.main()
