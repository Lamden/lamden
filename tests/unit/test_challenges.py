from unittest import TestCase
from lamden.crypto.challenges import create_challenge, verify_challenge
from lamden.crypto.wallet import Wallet


class TestWallet(TestCase):
    def test_create_challenge(self):
        challenge = create_challenge()

        print(challenge)

        self.assertEqual(25, len(challenge))
        self.assertIsInstance(challenge, str)

    def test_verify_challenge__returns_True_if_sig_valid(self):
        wallet = Wallet()

        challenge = create_challenge()
        challenge_response = wallet.sign(msg=challenge)

        self.assertTrue(verify_challenge(
            peer_vk=wallet.verifying_key,
            challenge=challenge,
            challenge_response=challenge_response
        ))

    def test_verify_challenge__returns_False_if_sig_valid(self):
        wallet = Wallet()
        wallet2 = Wallet()

        challenge = create_challenge()
        challenge_response = wallet.sign(msg=challenge)

        self.assertFalse(verify_challenge(
            peer_vk=wallet2.verifying_key,
            challenge=challenge,
            challenge_response=challenge_response
        ))

