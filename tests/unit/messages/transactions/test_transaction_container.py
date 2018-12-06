from unittest import TestCase

from cilantro.messages.transaction.base import MessageBase
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.transaction.contract import ContractTransactionBuilder
from cilantro.messages.transaction.container import TransactionContainer


class TestTransactionContainer(TestCase):
    def _convenience_build_standard_transaction(self):
        """These transactions get POSTed directly to masternodes by TAU wallet software"""
        tx = ContractTransactionBuilder.random_currency_tx()
        return tx

    def test_create_container(self):
        """Test creation of transaction container. Container must take an instance of messagebase and be a well-formatted
        transaction type to be accepted by masternode"""
        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)  # does not throw error

        self.assertTrue(type(tc), MessageBase)  # Transaction Container is a messagebase object

    def test_create_container_random_json(self):
        data = {'metadata': 'some_tx', 'type': 'standard', 'json': 'test'}
        cont = TransactionBase.from_data(data, validate=False)
        self.assertRaises(Exception, TransactionContainer.create, cont)  # random json packet throws exception

    def test_create_container_random_bytes(self):
        random_bytes = b'beezy'
        cont = TransactionBase.from_data(random_bytes, validate=False)
        self.assertRaises(Exception, TransactionContainer.create, cont)  # random bytes throws exception

    def test_create_container_invalid_transaction_base(self):
        data = 'lol'
        mb = MessageBase.from_data(data, validate=False)
        cont = TransactionBase.from_data(mb, validate=False)
        self.assertRaises(Exception, TransactionContainer.create, cont)  # fail b/c message base is not transaction base

    def test_serialize_container(self):
        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)
        tc.serialize() # does not throw error

    def test_deserialize_container(self):
        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)  # does not throw error
        tcs = tc.serialize()

        TransactionContainer.from_bytes(tcs)  # no error deserializing

    def test_open_container(self):
        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)
        open_container_data = tc.open()

        # test opened container for integrity
        open_container_data.validate_metadata()
        open_container_data.validate_payload()

    def test_open_container_bad_type(self):
        """Tests to see opening transaction container with invalid registry key fails"""
        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)
        tc._data.type = 9000  # set registry type to invalid entry
        self.assertRaises(Exception, tc.open)

    def test_open_container_bad_payload(self):
        """Tests to see opening transaction container with invalid registry key fails"""
        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)
        tc._data.payload = 'lel'  # set payload to invalid entry
        self.assertRaises(Exception, tc.open)
