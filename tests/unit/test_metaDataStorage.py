from unittest import TestCase
from cilantro_ee.storage.state import MetaDataStorage


class TestMetaDataStorage(TestCase):
    def setUp(self):
        self.db = MetaDataStorage()

    def tearDown(self):
        self.db.flush()

    def test_init(self):
        self.assertIsNotNone(self.db)
