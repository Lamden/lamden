from cilantro_ee.crypto.transaction import TransactionBuilder, verify_packed_tx
from unittest import TestCase
from cilantro_ee.crypto.wallet import Wallet
import os
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas

import capnp
transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


class TestContractTransaction(TestCase):
    def test_init(self):
        w = Wallet()
        TransactionBuilder(sender=w.verifying_key().hex(),
                           stamps=1000000,
                           contract='currency',
                           function='transfer',
                           kwargs={'amount': 'b'},
                           processor=b'\x00' * 32,
                           nonce=0)

    def test_signing_flips_true(self):
        w = Wallet()
        tx = TransactionBuilder(sender=w.verifying_key().hex(),
                                stamps=1000000,
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 'b'},
                                processor=b'\x00'*32,
                                nonce=0)

        self.assertFalse(tx.tx_signed)

        tx.sign(w.signing_key())

        self.assertTrue(tx.tx_signed)

    def test_generate_proof_flips_true(self):
        w = Wallet()
        tx = TransactionBuilder(sender=w.verifying_key().hex(),
                                stamps=1000000,
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 'b'},
                                processor=b'\x00'*32,
                                nonce=0)

        self.assertFalse(tx.proof_generated)

        tx.generate_proof()

        self.assertTrue(tx.proof_generated)

    def test_serialize_if_not_signed_returns_none(self):
        w = Wallet()
        tx = TransactionBuilder(sender=w.verifying_key().hex(),
                                stamps=1000000,
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 'b'},
                                processor=b'\x00'*32,
                                nonce=0)

        self.assertIsNone(tx.serialize())

    def test_serialize_returns_bytes(self):
        w = Wallet()
        tx = TransactionBuilder(sender=w.verifying_key().hex(),
                                stamps=1000000,
                                contract='currency',
                                function='transfer',
                                kwargs={'amount': 'b'},
                                processor=b'\x00'*32,
                                nonce=0)

        tx.sign(w.signing_key())

        tx_packed = tx.serialize()

        self.assertTrue(verify_packed_tx(w.verifying_key(), tx_packed))

    def test_bad_bytes_returns_false_on_verify(self):
        w = Wallet()
        b = b'bad'
        self.assertFalse(verify_packed_tx(w.verifying_key(), b))

    def test_passing_float_in_contract_kwargs_raises_assertion(self):
        w = Wallet()
        with self.assertRaises(AssertionError):
            TransactionBuilder(sender=w.verifying_key().hex(),
                               stamps=1000000,
                               contract='currency',
                               function='transfer',
                               kwargs={'amount': 123.00},
                               processor=b'\x00' * 32,
                               nonce=0)

    def test_passing_non_supported_type_in_contract_kwargs_raises_assertion(self):
        w = Wallet()
        with self.assertRaises(AssertionError):
            TransactionBuilder(sender=w.verifying_key().hex(),
                               stamps=1000000,
                               contract='currency',
                               function='transfer',
                               kwargs={'amount': ['b']},
                               processor=b'\x00'*32,
                               nonce=0)
# def __init__(self, sender, contract: str, function: str, kwargs: dict, stamps: int, processor: bytes,
#                  nonce: int):