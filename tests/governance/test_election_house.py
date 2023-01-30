from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from lamden.contracts import sync
from pathlib import Path
from unittest import TestCase

def test_policy():
    value = Variable()
    @construct
    def seed():
        value.set('1234')

    @export
    def current_value():
        return value.get()

    @export
    def vote(vk: str, obj: Any):
        value.set(obj)

    def another_func():
        pass


def bad_interface():
    @export
    def current_value():
        return 0

class TestBetterElectionHouse(TestCase):
    def setUp(self):
        self.contract_driver = ContractDriver(driver=FSDriver(root=Path('/tmp/temp_filebased_state')))
        self.client = ContractingClient(driver=self.contract_driver)
        self.client.flush()

        with open(sync.DEFAULT_PATH + '/genesis/election_house.s.py') as f:
            self.client.submit(f.read(), name='election_house2')

        self.election_house = self.client.get_contract('election_house2')

    def tearDown(self):
        self.client.flush()

    def test_register_doesnt_fail(self):
        self.client.submit(test_policy, owner='election_house2')
        self.election_house.register_policy(contract='test_policy')

    def test_register_without_owner_fails(self):
        self.client.submit(test_policy)
        with self.assertRaises(AssertionError):
            self.election_house.register_policy(contract='test_policy')

    def test_register_same_contract_twice_fails(self):
        self.client.submit(test_policy, owner='election_house2')
        self.election_house.register_policy(contract='test_policy')

        with self.assertRaises(Exception):
            self.election_house.register_policy(contract='test_policy')

    def test_register_contract_without_entire_interface_fails(self):
        self.client.submit(test_policy, owner='election_house2')

        with self.assertRaises(Exception):
            self.election_house.register_policy(policy='testing', contract='bad_interface')

    def test_register_same_contract_under_another_name_fails(self):
        self.client.submit(test_policy, owner='election_house2')
        self.election_house.register_policy(contract='test_policy')

        with self.assertRaises(Exception):
            self.election_house.register_policy(contract='test_policy')

    def test_current_value_for_policy_returns_correct_value(self):
        self.client.submit(test_policy, owner='election_house2')
        self.election_house.register_policy(contract='test_policy')

        res = self.election_house.current_value_for_policy(policy='test_policy')

        self.assertEqual(res, '1234')

    def test_current_value_for_non_existant_policy_fails(self):
        self.client.submit(test_policy, owner='election_house2')

        with self.assertRaises(AssertionError):
            self.election_house.current_value_for_policy(policy='testing')

    def test_vote_delegate_calls_policy(self):
        self.client.submit(test_policy, owner='election_house2')
        self.election_house.register_policy(contract='test_policy')
        self.election_house.vote(policy='test_policy', value='5678')

    def test_full_vote_flow_works(self):
        self.client.submit(test_policy, owner='election_house2')
        self.election_house.register_policy(contract='test_policy')
        self.election_house.vote(policy='test_policy', value='5678')

        res = self.election_house.current_value_for_policy(policy='test_policy')

        self.assertEqual(res, '5678')