from cilantro import Constants
from unittest import TestCase
from cilantro.models import StandardTransaction
from cilantro.models.transaction.standard import StandardTransactionBuilder
from cilantro.models.utils import int_to_decimal


class TestStandardTransaction(TestCase):

    @staticmethod
    def create_tx_struct(amount):
        """
        Helper method to create and return a valid transaction struct with a random sender/receiever and
        the specified amount
        """
        s = Constants.Protocol.Wallets.new()
        r = Constants.Protocol.Wallets.new()
        return StandardTransactionBuilder.create_tx_struct(s[0], s[1], r[1], amount)

    def __assert_struct_equal_object(self, tx_struct: object, tx_object: StandardTransaction):
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
        tx_struct = TestStandardTransaction.create_tx_struct(3.14)
        tx = StandardTransaction.from_bytes(tx_struct.to_bytes_packed(), validate=False)
        self.__assert_struct_equal_object(tx_struct, tx)

    def test_from_bytes_invalid(self):
        """
         Tests from_bytes with an invalid capnp struct (which in this case is just arbitrary bytes)
         """
        b = b'abcdefghijklmnopqrstuvwxyz'
        self.assertRaises(Exception, StandardTransaction.from_bytes, b, False)

    def test_from_data(self):
        """
        Tests from_data with a valid capnp struct (no validation)
        """
        tx_struct = TestStandardTransaction.create_tx_struct(250)
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.__assert_struct_equal_object(tx_struct, tx)

    def test_validation(self):
        """
        Tests that all validation passes with a correct struct
        """
        tx_struct = TestStandardTransaction.create_tx_struct(333)
        tx = StandardTransaction.from_data(tx_struct, validate=True)
        self.assertTrue(True)

    def test_invalid_pow(self):
        """
        Tests that an exception is thrown when given an invalid proof
        """
        # Test invalid type (non hex)
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.metadata.proof = ''.join(['X' for _ in range(32)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_pow)

        # Test invalid length
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.metadata.proof = ''.join(['a' for _ in range(30)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_pow)

        # Test invalid proof
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.metadata.proof = ''.join(['a' for _ in range(32)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_pow)

    def test_invalid_signature(self):
        """
        Tests that an exception is thrown when given an invalid signature
        """
        # Test invalid type (non hex)
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.metadata.signature = ''.join(['X' for _ in range(128)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_signature)

        # Test invalid length
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.metadata.signature = ''.join(['X' for _ in range(44)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_signature)

        # Test invalid signature
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.metadata.signature = ''.join(['a' for _ in range(128)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_signature)

    def test_invalid_payload_sender(self):
        """
        Tests that an exception is thrown when given an invalid sender
        """
        # Test invalid type (non hex)
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.payload.sender = ''.join(['X' for _ in range(64)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

        # Test invalid length
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.payload.sender = ''.join(['a' for _ in range(50)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_invalid_payload_receiver(self):
        """
        Tests that an exception is thrown when given an invalid receiver
        """
        # Test invalid type (non hex)
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.payload.sender = ''.join(['X' for _ in range(64)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

        # Test invalid length
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        tx_struct.payload.sender = ''.join(['a' for _ in range(50)])
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_invalid_payload_amount(self):
        """
        Tests that an exception is thrown when given an invalid amount. Note we don't have to check if amount is negative
        explicity because amount is stored as a 64 bit unsigned integer, and trying to assign it to a negative signed
        integer value will throw an exception.
        """
        # Test amount is 0
        tx_struct = TestStandardTransaction.create_tx_struct(0)
        print(tx_struct)
        tx = StandardTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_serialization(self):
        """
        Tests that serialize and from_bytes are inverse operations
        """
        tx_struct = TestStandardTransaction.create_tx_struct(100)
        struct_binary = tx_struct.to_bytes_packed()
        tx = StandardTransaction.from_data(tx_struct, validate=False)
