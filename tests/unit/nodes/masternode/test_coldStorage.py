from unittest import TestCase
from cilantro_ee.nodes.masternode.master_store import ColdStorage
from cilantro_ee.storage.vkbook import PhoneBook


class TestColdStorage(TestCase):
    def setUp(self):
        self.c = ColdStorage()

    def test_initialize(self):
        self.assertIsNotNone(self.c.config.test_hook)

    def test_get_masterset_test_hook_false(self):
        self.c.config.test_hook = False

        self.assertEqual(len(PhoneBook.masternodes), self.c.get_master_set())

    def test_get_masterset_test_hook_true(self):
        am = self.c.config.active_masters

        self.c.config.test_hook = True

        self.assertEqual(am, self.c.get_master_set())

    def test_set_mn_id_test_hook_true(self):
        mn_id = self.c.config.mn_id

        self.c.config.test_hook = True

        self.assertEqual(mn_id, self.c.set_mn_id(vk='0'))

    def test_set_mn_id_test_hook_false_master_not_in_active_masters(self):
        vk = 'IMPOSSIBLE WALLET'

        self.c.config.test_hook = False

        success = self.c.set_mn_id(vk)

        self.assertEqual(self.c.config.mn_id, -1)
        self.assertFalse(success)

    def test_set_mn_id_test_hook_false_master_in_active_masters(self):
        vk = PhoneBook.masternodes[0]

        self.c.config.test_hook = False

        success = self.c.set_mn_id(vk)

        self.assertEqual(self.c.config.mn_id, 0)
        self.assertTrue(success)

