from unittest import TestCase
from cilantro_ee.nodes.masternode.master_store import ColdStorage
from cilantro_ee.storage.vkbook import PhoneBook, VKBook
from cilantro_ee.protocol import wallet


class TestColdStorage(TestCase):
    def setUp(self):
        sk, vk = wallet.new()
        self.c = ColdStorage(key=sk)

    def tearDown(self):
        self.c.driver.drop_db()

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

    def test_rep_pool_size_fails_when_active_masters_less_than_rep_factor(self):
        self.c.config.rep_factor = 999
        self.assertEqual(self.c.rep_pool_sz(), -1)

    def test_rep_pool_size_returns_correctly_rounded_pool_size_when_enough_masters_present(self):
        self.c.config.test_hook = True

        self.c.config.rep_factor = 1
        pool = round(self.c.config.active_masters / self.c.config.rep_factor)
        self.assertEqual(self.c.rep_pool_sz(), pool)

    def test_build_write_list_returns_all_mns_when_jump_idx_0(self):
        mns = PhoneBook.masternodes

        self.assertEqual(mns, self.c.build_wr_list(None, 0))

    def test_build_write_list_curr_node_0_jump_idx_1_returns_all(self):
        masternodes = list(range(100))
        delegates = list(range(10))
        big_vkbook = VKBook(masternodes, delegates, stamps=True, nonces=True, debug=True)

        self.c.vkbook = big_vkbook

        write_list = self.c.build_wr_list(0, 1)
        self.assertEqual(masternodes, write_list)

    def test_build_write_list_curr_node_20_jump_idx_1_returns_subset(self):
        masternodes = list(range(100))
        delegates = list(range(10))
        big_vkbook = VKBook(masternodes, delegates, stamps=True, nonces=True, debug=True)

        self.c.vkbook = big_vkbook

        write_list = self.c.build_wr_list(20, 1)
        self.assertEqual(masternodes[20:], write_list)

    def test_update_index(self):
        block = {
            'blockNum': 100,
            'blockHash': 'a',
            'data': 'woohoo'
        }

        owners = ['tejas', 'stu']

        res = self.c.update_idx(block, owners)

        stored_index = self.c.driver.indexes.collection.find_one({
            'blockNum': 100
        })

        self.assertTrue(res)
        self.assertEqual(stored_index['blockOwners'], owners)

    def test_update_index_no_owners(self):
        block = {
            'blockNum': 100,
            'blockHash': 'a',
            'data': 'woohoo'
        }

        with self.assertRaises(AssertionError):
            self.c.update_idx(block, None)

    def test_update_index_no_block_hash(self):
        block = {
            'blockNum': 100,
            'data': 'woohoo'
        }

        with self.assertRaises(AssertionError):
            self.c.update_idx(block, ['tejas', 'stu'])

    def test_update_index_fails_with_no_block_num(self):
        block = {
            'blockHash': 'a',
            'data': 'woohoo'
        }

        with self.assertRaises(AssertionError):
            self.c.update_idx(block, ['tejas', 'stu'])

    def test_build_write_list_jump_idx_2_skips(self):
        masternodes = list(range(100))
        delegates = list(range(10))
        big_vkbook = VKBook(masternodes, delegates, stamps=True, nonces=True, debug=True)

        self.c.vkbook = big_vkbook

        write_list = self.c.build_wr_list(20, 2)
        self.assertEqual(masternodes[20::2], write_list)

    def test_evaluate_write_no_entry_returns_false(self):
        self.assertFalse(self.c.evaluate_wr())

    def test_evaluate_write_always_write_if_too_few_masters(self):
        self.c.config.active_masters = 1
        self.c.config.quorum_needed = 4

        block = {
            'blockNum': 103,
            'blockHash': 'a',
            'data': 'woohoo'
        }

        self.c.evaluate_wr(block)

        stored_block = self.c.driver.blocks.collection.find_one(block)

        self.assertEqual(stored_block, block)

        stored_index = self.c.driver.indexes.collection.find_one({'blockNum': 103})

        owners = self.c.build_wr_list(self.c.config.mn_id, 0)

        self.assertEqual(stored_index['blockOwners'], owners)
        self.assertEqual(stored_index['blockHash'], block['blockHash'])
        self.assertEqual(stored_index['blockNum'], block['blockNum'])

    def test_eval_write_node_id_is_in_writers_returns_true(self):
        self.c.config.rep_factor = 1

        block = {
            'blockNum': 100,
            'blockHash': 'a',
            'data': 'woohoo'
        }

        res = self.c.evaluate_wr(block, node_id=0)

        self.assertTrue(res)

    def test_eval_write_node_id_is_not_in_writers_returns_false(self):
        self.c.config.rep_factor = 1

        block = {
            'blockNum': 100,
            'blockHash': 'a',
            'data': 'woohoo'
        }

        res = self.c.evaluate_wr(block, node_id=1)

        self.assertFalse(res)

    def test_eval_write_if_mn_is_writer_then_write_block(self):
        self.c.config.rep_factor = 1

        block = {
            'blockNum': 100,
            'blockHash': 'a',
            'data': 'woohoo'
        }

        self.c.evaluate_wr(block)

        stored_block = self.c.driver.blocks.collection.find_one({'blockNum': 100})
        stored_index = self.c.driver.indexes.collection.find_one({'blockNum': 100})

        self.assertEqual(block, stored_block)

        self.assertEqual(stored_index['blockHash'], block['blockHash'])
        self.assertEqual(stored_index['blockNum'], block['blockNum'])

