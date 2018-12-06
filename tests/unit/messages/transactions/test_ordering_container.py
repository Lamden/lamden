from unittest import TestCase
from unittest.mock import MagicMock
from cilantro.messages.transaction.ordering import *
from cilantro.messages.transaction.contract import *


class TestOrderingContainer(TestCase):

    def test_create(self):
        tx = ContractTransactionBuilder.random_currency_tx()
        oc = OrderingContainer.create(tx)

        self.assertEqual(oc.transaction, tx)

    def test_serialize_deserialize(self):
        tx = ContractTransactionBuilder.random_currency_tx()
        oc = OrderingContainer.create(tx)
        clone = OrderingContainer.from_bytes(oc.serialize())

        self.assertEqual(clone, oc)
