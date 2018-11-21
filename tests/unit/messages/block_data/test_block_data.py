from cilantro.messages.transaction.data import TransactionData
from cilantro.messages.transaction.contract import ContractTransactionBuilder, ContractTransaction
from unittest import TestCase
import unittest
from cilantro.constants.testnet import TESTNET_MASTERNODES
TEST_SK = TESTNET_MASTERNODES[0]['sk']

class TestBlockData(TestCase):

    def test_create(self):
        td = TransactionData.create(
            contract_tx=ContractTransactionBuilder.create_currency_tx(
                sender_sk=TEST_SK, receiver_vk='A' * 64, amount=10),
            status='SUCCESS', state='SET x 1')

        self.assertTrue(isinstance(td.contract_tx, ContractTransaction))

    def test_serialize_deserialize(self):
        td = TransactionData.create(
            contract_tx=ContractTransactionBuilder.create_currency_tx(
                sender_sk=TEST_SK, receiver_vk='A' * 64, amount=10),
            status='SUCCESS', state='SET x 1')
        clone = TransactionData.from_bytes(td.serialize())

        self.assertEqual(clone, td)

if __name__ == '__main__':
    unittest.main()
