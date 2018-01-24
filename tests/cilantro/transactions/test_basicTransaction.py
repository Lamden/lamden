from unittest import TestCase
from cilantro.transactions import BasicTransaction
from cilantro.wallets import ED25519Wallet
from cilantro.proofs.pow import TwofishPOW

class TestBasicTransaction(TestCase):
    def test_builder(self):
        (s, v) = ED25519Wallet.new()
        (s2, v2) = ED25519Wallet.new()
        transaction = BasicTransaction(ED25519Wallet, TwofishPOW)

        print(transaction)

        print(transaction.build(v2, 100, s, v))