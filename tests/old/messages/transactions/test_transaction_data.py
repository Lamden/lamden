from unittest import TestCase
from unittest.mock import MagicMock

from cilantro_ee.messages.transaction.contract import ContractTransaction, ContractTransactionBuilder
from cilantro_ee.messages.transaction.data import TransactionData, TransactionDataBuilder
from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
TEST_SK = TESTNET_MASTERNODES[0]['sk']


class TestTransactionData(TestCase):

    def test_create_with_contract_tx(self):
        tx = ContractTransactionBuilder.random_currency_tx()
        status = 'SUCC'
        state = 'SET GHU 10;'

        tx_data = TransactionData.create(contract_tx=tx, status=status, state=state)

        self.assertEqual(tx_data.transaction, tx)
        self.assertEqual(tx_data.status, status)
        self.assertEqual(tx_data.state, state)

    def test_serialize_deserialize(self):
        tx = ContractTransactionBuilder.random_currency_tx()
        status = 'SUCC'
        state = 'SET GHU 10;'

        tx_data = TransactionData.create(contract_tx=tx, status=status, state=state)
        clone = TransactionData.from_bytes(tx_data.serialize())

        self.assertEqual(tx_data, clone)

    def test_create(self):
        td = TransactionData.create(
            contract_tx=ContractTransactionBuilder.create_currency_tx(
                sender_sk=TEST_SK, receiver_vk='A' * 64, amount=10),
            status='SUCCESS', state='SET x 1')

        self.assertTrue(isinstance(td.transaction, ContractTransaction))

    def test_serialize_deserialize2(self):
        td = TransactionData.create(
            contract_tx=ContractTransactionBuilder.create_currency_tx(
                sender_sk=TEST_SK, receiver_vk='A' * 64, amount=10),
            status='SUCCESS', state='SET x 1')
        clone = TransactionData.from_bytes(td.serialize())

        self.assertEqual(clone, td)

    def test_serialize_deserialize_consistent_hash(self):
        td = TransactionData.create(
            contract_tx=ContractTransactionBuilder.create_currency_tx(
                sender_sk=TEST_SK, receiver_vk='A' * 64, amount=10),
            status='SUCCESS', state='SET x 1')
        clone = TransactionData.from_bytes(td.serialize())

        self.assertEqual(clone.hash, td.hash)
