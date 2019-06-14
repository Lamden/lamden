from unittest import TestCase
from cilantro_ee.storage.mongo import MasterDatabase


class TestMasterDatabase(TestCase):
    def test_init_masterdatabase(self):
        m = MasterDatabase
