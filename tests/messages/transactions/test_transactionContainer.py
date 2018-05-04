from unittest import TestCase

from cilantro.messages import TransactionContainer, TransactionBase, MessageBase
from cilantro.messages import StandardTransactionBuilder
from cilantro.protocol.wallets import ED25519Wallet


class TransactionContainerTest(TestCase):
    def _convenience_build_standard_transaction(self):
        """These transactions get POSTed directly to masternodes by TAU wallet software"""
        STU = (ED25519Wallet.new())
        DAVIS = (ED25519Wallet.new())
        DENTON = (ED25519Wallet.new())
        FALCON = (ED25519Wallet.new())
        KNOWN_ADRS = (STU, DAVIS, DENTON, FALCON)
        amount = 10

        tx = StandardTransactionBuilder.create_tx(STU[0], STU[1], DAVIS[1], amount)
        return tx

    def test_create_container(self):
        """Test creation of transaction container. Container must take an instance of messagebase and be a well-formatted
        transaction type to be accepted by masternode"""
        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)  # does not throw error

        print(tc._data)

        self.assertTrue(type(tc), MessageBase)  # Transaction Container is a messagebase object



    def test_create_container_bad_input(self):
        data = {'metadata': 'some_tx', 'type': 'standard', 'json': 'test'}
        cont = TransactionBase.from_data(data, validate=False)

        # pass in valid messagebase class that is not a valid transaction base
        # should fail b/c message base is not transaction base

        # pass in random binary string

        self.assertRaises(Exception, TransactionContainer.create, cont)  # bad tx format throws exception

    def test_serialize_container(self):
        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)  # does not throw error
        tc.serialize()

    def test_deserialize_container(self):
        """Implemented in the MessageBase base class - does it need additional tests?"""
        tx = self._convenience_build_standard_transaction()

        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)  # does not throw error
        tcs = tc.serialize()

        tcd = TransactionContainer.from_bytes(tcs)

    def test_open_container(self):
        tx = self._convenience_build_standard_transaction()
        tc = TransactionContainer.create(tx)
        open_container_data = tc.open()
        # print(open_container_data)

        # test opened container for integrity
        open_container_data.validate_metadata()
        open_container_data.validate_payload()

    def test_open_container_fail_payload(self):
        # invalid binary
        # type 32668
        pass

    def test_open_container_bad_type(self):
        # set type to 9000
        pass

