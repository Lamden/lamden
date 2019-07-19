from cilantro_ee.messages._new.transactions.messages import ContractTransaction
from unittest import TestCase
from cilantro_ee.protocol.wallet import Wallet


class TestContractTransaction(TestCase):
    def test_init(self):
        ContractTransaction('blah', 123, 'blah', 'blah', 'blah', {'something': 123})

    def test_signing_with_correct_wallet_verifies(self):
        w = Wallet()
        tx = ContractTransaction(w.verifying_key().hex(),
                                 1000000, 'currency', 'transfer', 'test',
                                 {'amount': 123})

        self.assertFalse(tx.tx_signed)

        tx.sign(w.signing_key().hex())

        self.assertTrue(tx.tx_signed)