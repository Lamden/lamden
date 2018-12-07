from unittest import TestCase
from unittest.mock import MagicMock

from cilantro.messages.transaction.contract import ContractTransaction, ContractTransactionBuilder
from cilantro.messages.transaction.data import TransactionData, TransactionDataBuilder


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

