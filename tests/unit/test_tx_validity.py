from unittest import TestCase
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.protocol.transaction import TransactionBuilder


class TestTXValidity(TestCase):
    def setUp(self):
        self.driver = MetaDataStorage()
        self.driver.flush()

    def tearDown(self):
        self.driver.flush()

    def test_init(self):
        pass