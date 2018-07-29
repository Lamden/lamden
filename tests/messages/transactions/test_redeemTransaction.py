from cilantro import Constants
from unittest import TestCase
from cilantro.messages import RedeemTransaction, RedeemTransactionBuilder
from cilantro.messages.utils import int_to_decimal
import secrets
from cilantro.protocol.wallet import Wallet

class TestRedeemTransaction(TestCase):
    @staticmethod
    def create_tx_struct():
        """
        Helper method to create and return a valid transaction struct with a random sender/receiever and
        the specified amount
        """
        s = Wallet.new()
        return RedeemTransactionBuilder.create_tx_struct(s[0], s[1], secrets.token_hex(32))

    def __assert_struct_equal_object(self, tx_struct: object, tx_object: RedeemTransaction):
        """
        Helper method to assert the the attributes of the captain proto transaction struct are equal to the transaction
        object's attributes
        """
        self.assertEqual(tx_struct.metadata.proof.decode(), tx_object.proof)
        self.assertEqual(tx_struct.metadata.signature.decode(), tx_object.signature)
        self.assertEqual(tx_struct.payload.sender.decode(), tx_object.sender)
        self.assertEqual(tx_struct.payload.secret.decode(), tx_object.secret)

    def test_from_bytes(self):
        """
        Tests from_bytes with a valid serialized capnp struct (no validation)
        """
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx = RedeemTransaction.from_bytes(tx_struct.to_bytes_packed(), validate=False)
        self.__assert_struct_equal_object(tx_struct, tx)

    def test_from_bytes_invalid(self):
        """
         Tests from_bytes with an invalid capnp struct (which in this case is just arbitrary bytes)
         """
        b = b'abcdefghijklmnopqrstuvwxyz'
        self.assertRaises(Exception, RedeemTransaction.from_bytes, b, False)

    def test_from_data(self):
        """
        Tests from_data with a valid capnp struct (no validation)
        """
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.__assert_struct_equal_object(tx_struct, tx)

    def test_validation(self):
        """
        Tests that all validation passes with a correct struct
        """
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx = RedeemTransaction.from_data(tx_struct, validate=True)
        self.assertTrue(True)

    def test_invalid_pow(self):
        """
        Tests that an exception is thrown when given an invalid proof
        """
        # Test invalid type (non hex)
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.metadata.proof = ''.join(['X' for _ in range(32)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_pow)

        # Test invalid length
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.metadata.proof = ''.join(['a' for _ in range(30)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_pow)

        # Test invalid proof
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.metadata.proof = ''.join(['a' for _ in range(32)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_pow)

    def test_invalid_signature(self):
        """
        Tests that an exception is thrown when given an invalid signature
        """
        # Test invalid type (non hex)
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.metadata.signature = ''.join(['X' for _ in range(128)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_signature)

        # Test invalid length
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.metadata.signature = ''.join(['X' for _ in range(44)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_signature)

        # Test invalid signature
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.metadata.signature = ''.join(['a' for _ in range(128)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_signature)

    def test_invalid_payload_sender(self):
        """
        Tests that an exception is thrown when given an invalid sender
        """
        # Test invalid type (non hex)
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.payload.sender = ''.join(['X' for _ in range(64)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

        # Test invalid length
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.payload.sender = ''.join(['a' for _ in range(50)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_invalid_payload_receiver(self):
        """
        Tests that an exception is thrown when given an invalid receiver
        """
        # Test invalid type (non hex)
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.payload.sender = ''.join(['X' for _ in range(64)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

        # Test invalid length
        tx_struct = TestRedeemTransaction.create_tx_struct()
        tx_struct.payload.sender = ''.join(['a' for _ in range(50)])
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
        self.assertRaises(Exception, tx.validate_payload)

    def test_serialization(self):
        """
        Tests that serialize and from_bytes are inverse operations
        """
        tx_struct = TestRedeemTransaction.create_tx_struct()
        struct_binary = tx_struct.to_bytes_packed()
        tx = RedeemTransaction.from_data(tx_struct, validate=False)
