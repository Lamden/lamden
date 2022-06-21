from lamden import storage
from unittest import TestCase
import json
import decimal


class TestMisc(TestCase):
    def setUp(self):
        self.client = storage.BlockStorage()
        self.client.flush()

    def tearDown(self):
        self.client.flush()

    def test_storing_large_int(self):
        block = {
            'data': 1_000_000_000_000_000_000_000_000_000_000
        }

        b = json.dumps(block)
        _b = json.loads(b, parse_int=decimal.Decimal)

        self.client.store_block(_b)
