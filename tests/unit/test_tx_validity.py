from unittest import TestCase
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.protocol.transaction import TransactionBuilder, transaction_is_valid
from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.messages import capnp as schemas

import secrets
import os
import capnp

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


class TestTXValidity(TestCase):
    def setUp(self):
        self.driver = MetaDataStorage()
        self.driver.flush()

    def tearDown(self):
        self.driver.flush()

    def test_processor_incorrect_returns_false(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)
        given_processor = secrets.token_bytes(32)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=given_processor,
                                nonce=0)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertFalse(is_valid)

    def test_processor_is_expected_but_nonce_is_incorrect_returns_false(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=1)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertFalse(is_valid)

    def test_processor_and_nonce_correct_increments_pending_nonce_by_one(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=0)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        pending_nonce = self.driver.get_pending_nonce(expected_processor, w.verifying_key())

        self.assertFalse(is_valid)
        self.assertEqual(pending_nonce, 1)

    def test_processor_and_nonce_correct_but_not_enough_stamps_returns_false(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=0)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertFalse(is_valid)