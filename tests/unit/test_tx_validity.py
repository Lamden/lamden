from unittest import TestCase
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.protocol.transaction import TransactionBuilder, transaction_is_valid
from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.messages import capnp as schemas
from contracting import config
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
                                stamps=0,
                                processor=expected_processor,
                                nonce=0)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        pending_nonce = self.driver.get_pending_nonce(expected_processor, w.verifying_key())

        self.assertTrue(is_valid)
        self.assertEqual(pending_nonce, 1)

    def test_all_but_wallet_signed_returns_false(self):
        w = Wallet()
        x = Wallet()

        expected_processor = secrets.token_bytes(32)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=0,
                                processor=expected_processor,
                                nonce=0)

        tx.sign(x.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertFalse(is_valid)

    def test_all_but_proof_valid_returns_false(self):
        w = Wallet()

        expected_processor = secrets.token_bytes(32)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=0,
                                processor=expected_processor,
                                nonce=0)

        tx.proof = b'\00' * 32
        tx.proof_generated = True

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertFalse(is_valid)

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

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           tx.payload.sender.hex())

        balance = self.driver.get(balances_key) or 0

        self.assertEqual(balance, 0)
        self.assertFalse(is_valid)

    def test_all_valid_with_stamps_when_balance_is_set(self):
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

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           tx.payload.sender.hex())

        self.driver.set(balances_key, 500000)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)
        balance = self.driver.get(balances_key) or 0

        self.assertEqual(balance, 500000)
        self.assertTrue(is_valid)

    def test_multiple_nonces_in_sequence_all_verify(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        self.driver.set(balances_key, 500000)

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

        self.assertTrue(is_valid)

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

        self.assertTrue(is_valid)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=2)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertTrue(is_valid)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=3)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertTrue(is_valid)

    def test_non_sequence_fails_in_strict_mode(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        self.driver.set(balances_key, 500000)

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

        self.assertTrue(is_valid)

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

        self.assertTrue(is_valid)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=2)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertTrue(is_valid)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=5)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertFalse(is_valid)

    def test_greater_than_passes_in_no_strict_mode(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        self.driver.set(balances_key, 500000)

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

        self.assertTrue(is_valid)

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

        self.assertTrue(is_valid)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=2)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertTrue(is_valid)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=5)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver,
                                        strict=False)

        self.assertTrue(is_valid)

    def test_non_strict_fails_if_same_nonce(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        self.driver.set(balances_key, 500000)

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

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver,
                                        strict=False)

        self.assertTrue(is_valid)

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

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver,
                                        strict=False)

        self.assertFalse(is_valid)

    def test_strict_fails_if_same_nonce(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        self.driver.set(balances_key, 500000)

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

        self.assertTrue(is_valid)

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

    def test_tx_nonce_minus_nonce_less_than_tx_per_block(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        self.driver.set(balances_key, 500000)

        self.driver.set_nonce(processor=expected_processor, sender=w.verifying_key(), nonce=1)
        self.driver.set_pending_nonce(processor=expected_processor, sender=w.verifying_key(), nonce=2)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=2)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertTrue(is_valid)

    def test_tx_nonce_minus_nonce_greater_than_tx_per_block_fails(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        self.driver.set(balances_key, 500000)

        self.driver.set_nonce(processor=expected_processor, sender=w.verifying_key(), nonce=1)
        self.driver.set_pending_nonce(processor=expected_processor, sender=w.verifying_key(), nonce=10)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=20)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertFalse(is_valid)

    def test_nonce_minus_pending_nonce_equal_tx_per_block_fails(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        self.driver.set(balances_key, 500000)

        self.driver.set_nonce(processor=expected_processor, sender=w.verifying_key(), nonce=1)
        self.driver.set_pending_nonce(processor=expected_processor, sender=w.verifying_key(), nonce=16)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=16)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertFalse(is_valid)

    def test_15_in_row_valid_16th_not_due_to_tx_per_block_failing(self):
        w = Wallet()
        expected_processor = secrets.token_bytes(32)

        balances_key = '{}{}{}{}{}'.format('currency',
                                           config.INDEX_SEPARATOR,
                                           'balances',
                                           config.DELIMITER,
                                           w.verifying_key().hex())

        self.driver.set(balances_key, 500000)

        for i in range(15):
            tx = TransactionBuilder(w.verifying_key(),
                                    contract='currency',
                                    function='transfer',
                                    kwargs={'amount': 10, 'to': 'jeff'},
                                    stamps=500000,
                                    processor=expected_processor,
                                    nonce=i)

            tx.sign(w.signing_key())
            tx_bytes = tx.serialize()
            tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

            is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

            self.assertTrue(is_valid)

        tx = TransactionBuilder(w.verifying_key(),
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 10, 'to': 'jeff'},
                                stamps=500000,
                                processor=expected_processor,
                                nonce=15)

        tx.sign(w.signing_key())
        tx_bytes = tx.serialize()
        tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)

        is_valid = transaction_is_valid(tx=tx_struct, expected_processor=expected_processor, driver=self.driver)

        self.assertFalse(is_valid)
