import unittest
from unittest import TestCase
from os import listdir, makedirs
from os.path import exists, join
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519
from cilantro_ee.protocol.overlay.auth import Auth
from cilantro_ee.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES

class TestAuth(TestCase):
    def test_setup(self):
        sk, vk = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']
        Auth.setup(sk, reset_auth_folder=True)
        self.assertEqual(Auth.sk, sk)
        self.assertEqual(Auth.vk, vk)
        self.assertEqual(Auth.public_key, Auth.vk2pk(vk))
        self.assertEqual(Auth.private_key, crypto_sign_ed25519_sk_to_curve25519(Auth._sk._signing_key))

if __name__ == '__main__':
    unittest.main()
