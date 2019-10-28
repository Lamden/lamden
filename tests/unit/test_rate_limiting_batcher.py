from unittest import TestCase
from cilantro_ee.nodes.masternode.transaction_batcher import RateLimitingBatcher
from cilantro_ee.core.crypto.wallet import Wallet, _verify


class MockQueue:
    def __init__(self):
        self.q = []

    def get(self):
        return self.q.pop(0)


class TestRateLimitingBatcher(TestCase):
    def test_add_batch_id_adds_properly(self):
        r = RateLimitingBatcher(
            queue=MockQueue(),
            wallet=Wallet(),
            sleep_interval=0,
            max_batch_size=1,
            max_txn_delay=1
        )

        r.add_batch_id('123')

        self.assertListEqual(r.sent_batch_ids, ['123'])
        self.assertEqual(r.num_batches_sent, 1)

    def test_adding_multiple_batches_adjusts_accordingly(self):
        r = RateLimitingBatcher(
            queue=MockQueue(),
            wallet=Wallet(),
            sleep_interval=0,
            max_batch_size=1,
            max_txn_delay=1
        )

        r.add_batch_id('123')

        self.assertListEqual(r.sent_batch_ids, ['123'])
        self.assertEqual(r.num_batches_sent, 1)

        r.add_batch_id('567')

        self.assertListEqual(r.sent_batch_ids, ['123', '567'])
        self.assertEqual(r.num_batches_sent, 2)

    def test_adding_same_batch_ids_acts_like(self):
        # TBD
        pass

