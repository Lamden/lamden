from cilantro.messages.transaction.batch import TransactionBatch
from cilantro.messages.transaction.ordering import build_test_container
from unittest import TestCase


class TestTransactionBatch(TestCase):

    def test_empty_init(self):
        batch = TransactionBatch.create(None)

        self.assertTrue(batch.is_empty)

    def test_with_ordering_container(self):
        containers = [build_test_container() for _ in range(4)]
        batch = TransactionBatch.create(containers)

        self.assertEqual(batch.transactions, containers)
        self.assertFalse(batch.is_empty)

    def test_serialize_deserialize(self):
        containers = [build_test_container() for _ in range(4)]
        batch = TransactionBatch.create(containers)
        clone = TransactionBatch.from_bytes(batch.serialize())

        self.assertEqual(batch, clone)

    def test_create_with_non_ordering_container(self):
        not_containers = ['sup im a string. no OrderingContainer here, no sir', 'hi fren']
        
        self.assertRaises(AssertionError, TransactionBatch.create, not_containers)
