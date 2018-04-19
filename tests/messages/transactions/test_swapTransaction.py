from unittest import TestCase
from cilantro.messages import SwapTransaction, SwapTransactionBuilder
from cilantro.messages.utils import validate_hex, int_to_decimal
from cilantro import Constants
import secrets
import time

class TestSwapTransaction(TestCase):
    @staticmethod
    def create_tx_struct(amount, h=None, e=None):
        """
        Helper method to create and return a valid transaction struct with a random sender/receiver and
        the specified amount
        """

        hashlock = h if h is not None else secrets.token_bytes(64)
        expiration = e if e is not None else int(time.time()) + (60 * 60 * 24)

        s = Constants.Protocol.Wallets.new()
        r = Constants.Protocol.Wallets.new()

        return SwapTransactionBuilder.create_tx_struct(s[0], s[1], r[1], amount, hashlock, expiration)

    def __assert_struct_equal_object(self, tx_struct: object, tx_object: SwapTransaction):
        """
        Helper method to assert the the attributes of the captain proto transaction struct are equal to the transaction
        object's attributes
        """
        self.assertEqual(tx_struct.metadata.proof.decode(), tx_object.proof)
        self.assertEqual(tx_struct.metadata.signature.decode(), tx_object.signature)
        self.assertEqual(tx_struct.payload.sender.decode(), tx_object.sender)
        self.assertEqual(int_to_decimal(tx_struct.payload.amount), tx_object.amount)
        self.assertEqual(tx_struct.payload.receiver.decode(), tx_object.receiver)

    def test_from_bytes(self):
        """
        Tests from_bytes with a valid serialized capnp struct (no validation)
        """
        tx_struct = TestSwapTransaction.create_tx_struct(3.14)
        tx = SwapTransaction.from_bytes(tx_struct.to_bytes_packed(), validate=False)
        self.__assert_struct_equal_object(tx_struct, tx)

    def test_from_bytes_invalid(self):
        """
         Tests from_bytes with an invalid capnp struct (which in this case is just arbitrary bytes)
         """
        b = b'abcdefghijklmnopqrstuvwxyz'
        self.assertRaises(Exception, SwapTransaction.from_bytes, b, False)

    def test_from_data(self):
        """
        Tests from_data with a valid capnp struct (no validation)
        """
        tx_struct = TestSwapTransaction.create_tx_struct(250)
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.__assert_struct_equal_object(tx_struct, tx)

    def test_validation(self):
        """
        Tests that all validation passes with a correct struct
        """
        tx_struct = TestSwapTransaction.create_tx_struct(333)
        tx = SwapTransaction.from_data(tx_struct, validate=True)
        self.assertTrue(True)

    def test_invalid_pow(self):
        """
        Tests that an exception is thrown when given an invalid proof
        """
        # Test invalid type (non hex)
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.metadata.proof = ''.join(['X' for _ in range(32)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_pow)

        # Test invalid length
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.metadata.proof = ''.join(['a' for _ in range(30)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_pow)

        # Test invalid proof
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.metadata.proof = ''.join(['a' for _ in range(32)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_pow)

    def test_invalid_signature(self):
        """
        Tests that an exception is thrown when given an invalid signature
        """
        # Test invalid type (non hex)
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.metadata.signature = ''.join(['X' for _ in range(128)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_signature)

        # Test invalid length
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.metadata.signature = ''.join(['X' for _ in range(44)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_signature)

        # Test invalid signature
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.metadata.signature = ''.join(['a' for _ in range(128)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_signature)

    def test_invalid_payload_sender(self):
        """
        Tests that an exception is thrown when given an invalid sender
        """
        # Test invalid type (non hex)
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.payload.sender = ''.join(['X' for _ in range(64)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

        # Test invalid length
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.payload.sender = ''.join(['a' for _ in range(50)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_invalid_payload_receiver(self):
        """
        Tests that an exception is thrown when given an invalid receiver
        """
        # Test invalid type (non hex)
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.payload.sender = ''.join(['X' for _ in range(64)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

        # Test invalid length
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        tx_struct.payload.sender = ''.join(['a' for _ in range(50)])
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_invalid_payload_amount(self):
        """
        Tests that an exception is thrown when given an invalid amount. Note we don't have to check if amount is negative
        explicity because amount is stored as a 64 bit unsigned integer, and trying to assign it to a negative signed
        integer value will throw an exception.
        """
        # Test amount is 0
        tx_struct = TestSwapTransaction.create_tx_struct(0)
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_invalid_hashlock(self):
        """
        Tests that an exception is thrown when given an invalid hashlock. Hashlocks are at maximum 64 bytes long
        """
        # Test amount is 0
        tx_struct = TestSwapTransaction.create_tx_struct(1, secrets.token_bytes(128))
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_invalid_expiration(self):
        """
        Tests that an exception is thrown when given an invalid expiration. Expirations have to exist in the future
        """
        # Test amount is 0
        tx_struct = TestSwapTransaction.create_tx_struct(1, None, int(time.time())-1)
        tx = SwapTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_serialization(self):
        """
        Tests that serialize and from_bytes are inverse operations
        """
        tx_struct = TestSwapTransaction.create_tx_struct(100)
        struct_binary = tx_struct.to_bytes_packed()
        tx = SwapTransaction.from_data(tx_struct, validate=False)