from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from lamden.contracts import sync
from pathlib import Path
from unittest import TestCase

class TestCurrency(TestCase):
    def setUp(self):
        self.contract_driver = ContractDriver(driver=FSDriver(root=Path('/tmp/temp_filebased_state')))
        self.client = ContractingClient(driver=self.contract_driver)
        self.client.flush()

        with open(sync.DEFAULT_PATH + '/genesis/hash_lists.s.py') as f:
            self.client.submit(f.read(), name='hash_lists')

        self.hash_lists = self.client.get_contract('hash_lists')

        self.contract_driver.commit()

    def make_list(self, con_name: str, list_name: str, list_to_store: list, permission_to: str = None):
        for idx, val in enumerate(list_to_store):
            self.contract_driver.set(key=f'hash_lists.lists:{con_name}:{list_name}:{str(idx)}', value=val)

        self.contract_driver.set(key=f'hash_lists.lists:{con_name}:{list_name}:limiter', value=len(list_to_store))

        if permission_to is not None:
            self.contract_driver.set(key=f'hash_lists.lists:{con_name}:{list_name}:{permission_to}', value=True)

        self.contract_driver.commit()

    def tearDown(self):
        self.client.flush()

    ###
    # ASSERT CALLED BY CONTRACT
    def test_METHOD_assert_called_by_contract__asserts_not_called_by_contract(self):
        with self.assertRaises(AssertionError) as err:
            self.hash_lists.assert_called_by_contract( signer="22c5676c76d236e71b1b457aa5fa00cce2e11d5dbb04bfedcc43402920ee2e44")

        self.assertEqual("This method can only be called by contracts.", str(err.exception))

    def test_METHOD_assert_called_by_contract__is_called_by_contract(self):
        try:
            self.hash_lists.assert_called_by_contract( signer="con_valid")
        except AssertionError:
            self.fail("A caller starting with con_ should pass")

    ###
    # ASSERT PERMISSION
    def test_METHOD_assert_permission__asserts_no_permission(self):
        with self.assertRaises(AssertionError) as err:
            self.hash_lists.assert_permission(from_con_name="con_valid", list_name="test_list", signer="con_other")

        self.assertEqual("You do not have permission to modify list con_valid:test_list.", str(err.exception))

    def test_METHOD_assert_permission__contract_is_okay(self):
        self.contract_driver.set(key=f'hash_lists.lists:con_valid:test_list:con_other', value=True)
        self.contract_driver.commit()

        try:
            self.hash_lists.assert_permission(from_con_name="con_valid", list_name="test_list", signer="con_other")
        except AssertionError as err:
            print(str(err))
            self.fail("A caller with permission set to True should not fail this assert")

    ###
    # ASSERT RESERVED VALUES
    def test_METHOD_assert_reserved_values__asserts_value(self):
        with self.assertRaises(AssertionError) as err:
            self.hash_lists.assert_reserved_values(value="__del__", signer="con_valid")

        self.assertEqual("Cannot add value '__del__' to a list.", str(err.exception))

    def test_METHOD_assert_reserved_values__other_values_okay(self):
        try:
            self.hash_lists.assert_reserved_values(value="del", signer="con_valid")
        except AssertionError as err:
            print(str(err))
            self.fail("Any value except '__del__' should not fail this assert")

    ###
    # ASSERT LIST EXISTS
    def test_METHOD_assert_list_exists__asserts_no_permission(self):
        with self.assertRaises(AssertionError) as err:
            self.hash_lists.assert_list_exists(from_con_name="con_valid", list_name="test_list", signer="con_valid")

        self.assertEqual("List con_valid:test_list does not exist.", str(err.exception))

    def test_METHOD_assert_list_exists__contract_is_okay(self):
        self.contract_driver.set(key=f'hash_lists.lists:con_valid:test_list:limiter', value=1)
        self.contract_driver.commit()

        try:
            self.hash_lists.assert_list_exists(from_con_name="con_valid", list_name="test_list", signer="con_valid")
        except AssertionError as err:
            print(str(err))
            self.fail("A list with a limiter property should not fail this assert")

    ###
    # GET LIST
    def test_METHOD_get_list__returns_empty_list_if_not_exist(self):
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([], l)
        self.assertEqual(None, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))

    def test_METHOD_get_list__returns_list_by_caller(self):
        self.make_list("con_valid", "test_list", [1,2,3])
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,2,3], l)
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertIsInstance(l, list)

    def test_METHOD_get_list__returns_list_by_from(self):
        self.make_list("con_other", "test_list", [1,2,3])
        l = self.hash_lists.get_list(list_name="test_list", from_con_name="con_other", signer="con_valid")

        self.assertEqual([1,2,3], l)
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_other:test_list:limiter'))

    def test_METHOD_get_list__filters_out_deleted(self):
        self.make_list("con_valid", "test_list", [1,2, "__del__", 3])
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,2,3], l)
        self.assertEqual(4, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))

    ###
    # REMOVE BY INDEX
    def test_METHOD_remove_by_index__removes_value_at_specified_index(self):
        self.make_list("con_valid", "test_list", [1, 2, 3])

        self.hash_lists.remove_by_index(list_name="test_list", index=1, signer="con_valid")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,3], l)
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:1'))

    def test_METHOD_remove_by_index__removes_value_at_specified_index__from_con_name(self):
        self.make_list("con_valid", "test_list", [1, 2, 3], "con_other")

        self.hash_lists.remove_by_index(list_name="test_list", index=1, from_con_name="con_valid", signer="con_other")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,3], l)
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:1'))

    def test_METHOD_remove_by_index__removes_value_at_specified_index_after_del(self):
        self.make_list("con_valid", "test_list", [1, "__del__", 3, 4])

        self.hash_lists.remove_by_index(list_name="test_list", index=1, signer="con_valid")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,4], l)
        self.assertEqual(4, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:2'))

    def test_METHOD_remove_by_index__asserts_index_out_of_range(self):
        self.make_list("con_valid", "test_list", [1, 2, 3])

        with self.assertRaises(AssertionError) as err:
            self.hash_lists.remove_by_index(list_name="test_list", index=3, signer="con_valid")

        self.assertEqual("Index 3 out of max range 2.", str(err.exception))

    def test_METHOD_remove_by_index__asserts_virtual_index_out_of_range(self):
        self.make_list("con_valid", "test_list", [1, 2, "__del__", 4])

        with self.assertRaises(AssertionError) as err:
            self.hash_lists.remove_by_index(list_name="test_list", index=3, signer="con_valid")

        self.assertEqual("Virtual index 4 out of max range 3.", str(err.exception))

    ###
    # REMOVE BY VALUE
    def test_METHOD_remove_by_value__removes_one(self):
        self.make_list("con_valid", "test_list", [1, 2, 3])

        self.hash_lists.remove_by_value(list_name="test_list", value=2, signer="con_valid")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,3], l)
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:1'))

    def test_METHOD_remove_by_value__removes_one__from_con_name(self):
        self.make_list("con_valid", "test_list", [1, 2, 3], "con_other")

        self.hash_lists.remove_by_value(list_name="test_list", value=2, from_con_name="con_valid", signer="con_other")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,3], l)
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:1'))

    def test_METHOD_remove_by_value__removes_all(self):
        self.make_list("con_valid", "test_list", [1, 2, 3, 2])

        self.hash_lists.remove_by_value(list_name="test_list", value=2, remove_all=True, signer="con_valid")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,3], l)
        self.assertEqual(4, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:1'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:3'))

    ###
    # ADD TO LIST
    def test_METHOD_add_to_list__adds_a_value_in_first_del_spot(self):
        self.make_list("con_valid", "test_list", [1, 2, "__del__", 4, "__del__"])

        self.hash_lists.add_to_list(list_name="test_list", value=3, signer="con_valid")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,2,3,4], l)
        self.assertEqual(5, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:2'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:4'))

    def test_METHOD_add_to_list__adds_a_value_in_first_del_spot__from_con_name(self):
        self.make_list("con_valid", "test_list", [1, 2, "__del__", 4, "__del__"], "con_other")

        self.hash_lists.add_to_list(list_name="test_list", value=3,  from_con_name="con_valid", signer="con_other")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,2,3,4], l)
        self.assertEqual(5, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:2'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:4'))

    ###
    # ADD TO LIST
    def test_METHOD_append_to_list__adds_a_value_at_end(self):
        self.make_list("con_valid", "test_list", [1, 2, "__del__", 3, "__del__"])

        self.hash_lists.append_to_list(list_name="test_list", value=4, signer="con_valid")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,2,3,4], l)
        self.assertEqual(6, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual(4, self.hash_lists.quick_read('lists', 'con_valid:test_list:5'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:2'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:4'))

    def test_METHOD_append_to_list__adds_a_value_at_end__from_con_name(self):
        self.make_list("con_valid", "test_list", [1, 2, "__del__", 3, "__del__"], "con_other")

        self.hash_lists.append_to_list(list_name="test_list", value=4, from_con_name="con_valid", signer="con_other")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,2,3,4], l)
        self.assertEqual(6, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual(4, self.hash_lists.quick_read('lists', 'con_valid:test_list:5'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:2'))
        self.assertEqual("__del__", self.hash_lists.quick_read('lists', 'con_valid:test_list:4'))

    ###
    # STORE LIST
    def test_METHOD_store_list__stores_a_list(self):
        self.hash_lists.store_list(list_name="test_list", list_data=[1,2,3], signer="con_valid")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,2,3], l)
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual(1, self.hash_lists.quick_read('lists', 'con_valid:test_list:0'))
        self.assertEqual(2, self.hash_lists.quick_read('lists', 'con_valid:test_list:1'))
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:2'))

    def test_METHOD_store_list__stores_a_list__from_con_name(self):
        self.contract_driver.set(key=f'hash_lists.lists:con_valid:test_list:con_other', value=True)

        self.hash_lists.store_list(
            list_name="test_list",
            list_data=[1,2,3],
            from_con_name="con_valid",
            signer="con_other"
        )
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,2,3], l)
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual(1, self.hash_lists.quick_read('lists', 'con_valid:test_list:0'))
        self.assertEqual(2, self.hash_lists.quick_read('lists', 'con_valid:test_list:1'))
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:2'))

    def test_METHOD_store_list__overwrites_list(self):
        self.make_list("con_valid", "test_list", [1, 2, "__del__", 3, "__del__"])
        self.assertEqual(5, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))

        self.hash_lists.store_list(list_name="test_list", list_data=[1,2,3], signer="con_valid")
        l = self.hash_lists.get_list(list_name="test_list", signer="con_valid")

        self.assertEqual([1,2,3], l)
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:limiter'))
        self.assertEqual(1, self.hash_lists.quick_read('lists', 'con_valid:test_list:0'))
        self.assertEqual(2, self.hash_lists.quick_read('lists', 'con_valid:test_list:1'))
        self.assertEqual(3, self.hash_lists.quick_read('lists', 'con_valid:test_list:2'))

    ###
    # APPROVE
    def test_METHOD_approve__sets_approval_to_True(self):
        self.hash_lists.approve(list_name="test_list", to="con_other", signer="con_valid")
        self.assertEqual(True, self.hash_lists.quick_read('lists', 'con_valid:test_list:con_other'))

    ###
    # REVOKE
    def test_METHOD_revoke__sets_approval_to_True(self):
        self.hash_lists.revoke(list_name="test_list", to="con_other", signer="con_valid")
        self.assertEqual(False, self.hash_lists.quick_read('lists', 'con_valid:test_list:con_other'))

    def test_METHOD_revoke__is_denied_permission_after_revoke(self):
        self.hash_lists.revoke(list_name="test_list", to="con_other", signer="con_valid")
        self.assertEqual(False, self.hash_lists.quick_read('lists', 'con_valid:test_list:con_other'))

        with self.assertRaises(AssertionError) as err:
            self.hash_lists.assert_permission(from_con_name="con_valid", list_name="test_list", signer="con_other")

        self.assertEqual("You do not have permission to modify list con_valid:test_list.", str(err.exception))

