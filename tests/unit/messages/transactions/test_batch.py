from cilantro.messages.transaction.batch import TransactionBatch, build_test_transaction_batch
from cilantro.messages.transaction.ordering import build_test_container
from unittest import TestCase


class TestTransactionBatch(TestCase):

    def test_build_test_transaction_batch(self):
        non_empty_batch = build_test_transaction_batch(8)
        empty_batch = build_test_transaction_batch(0)

        self.assertTrue(empty_batch.is_empty)
        self.assertEqual(len(non_empty_batch.transactions), 8)

    def test_empty_init(self):
        batch = TransactionBatch.create(None)

        self.assertTrue(batch.is_empty)

    def test_empty_list_init(self):
        batch = TransactionBatch.create([])

        self.assertTrue(batch.is_empty)

    def test_with_ordering_container(self):
        containers = [build_test_container() for _ in range(4)]
        batch = TransactionBatch.create(containers)

        self.assertEqual(batch.ordered_transactions, containers)
        self.assertFalse(batch.is_empty)

    def test_serialize_deserialize(self):
        containers = [build_test_container() for _ in range(4)]
        batch = TransactionBatch.create(containers)
        clone = TransactionBatch.from_bytes(batch.serialize())

        self.assertEqual(batch, clone)
        self.assertEqual(clone.ordered_transactions, containers)

    def test_create_with_non_ordering_container(self):
        not_containers = ['sup im a string. no OrderingContainer here, no sir', 'hi fren']
        
        self.assertRaises(AssertionError, TransactionBatch.create, not_containers)
