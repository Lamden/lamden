from unittest import TestCase
from cilantro.protocol.interpreters import TransactionType

class TestTransactionType(TestCase):
    def test_matching_transaction_type(self):
        test_type = TransactionType('test', ['key1', 'key2', 'key3'])
        matching_tx = {
            'type': 'test',
            'key1': None,
            'key2': None,
            'key3': None
        }
        self.assertTrue(test_type.is_transaction_type(matching_tx))

    def test_matching_transaction_keys_but_bad_type(self):
        test_type = TransactionType('test', ['key1', 'key2', 'key3'])
        matching_tx = {
            'type': 'not_test',
            'key1': None,
            'key2': None,
            'key3': None
        }
        self.assertFalse(test_type.is_transaction_type(matching_tx))

    def test_not_matching_transaction(self):
        test_type = TransactionType('test', ['key1', 'key2', 'key3'])
        matching_tx = {
            'type': 'not_test',
            'key4': None,
            'key2': None,
            'key3': None
        }
        self.assertFalse(test_type.is_transaction_type(matching_tx))