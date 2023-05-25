from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from contracting.stdlib.bridge.time import Datetime
from datetime import datetime as dt, timedelta as td
import math
from lamden.contracts import sync
from pathlib import Path
import os
from unittest import TestCase
from lamden.nodes.hlc import HLC_Clock

class TestMembers(TestCase):
    def setUp(self):
        self.hlc_clock = HLC_Clock()
        submission_file_path = os.path.join(Path.cwd().parent, 'integration','mock','submission.py')
        self.contract_driver = ContractDriver(driver=FSDriver(root=Path('/tmp/temp_filebased_state')))
        self.client = ContractingClient(driver=self.contract_driver, submission_filename=submission_file_path)
        self.client.flush()

        f = open(sync.DEFAULT_PATH + '/genesis/currency.s.py')
        self.client.submit(f.read(), 'currency', constructor_args={'vk': 'test'})
        f.close()

        with open(sync.DEFAULT_PATH + '/genesis/election_house.s.py') as f:
            contract = f.read()

        self.client.submit(contract, name='election_house')

        f = open(sync.DEFAULT_PATH + '/genesis/elect_members.s.py')
        self.client.submit(f.read(), 'elect_members', constructor_args={'policy': 'masternodes'})
        f.close()

        f = open(sync.DEFAULT_PATH + '/genesis/stamp_cost.s.py')
        self.client.submit(f.read(), 'stamp_cost', owner='election_house', constructor_args={'initial_rate': 20_000})
        f.close()

        self.election_house = self.client.get_contract('election_house')
        self.stamp_cost = self.client.get_contract(name='stamp_cost')
        self.election_house.register_policy(contract='stamp_cost')
        self.elect_members = self.client.get_contract('elect_members')
        self.currency = self.client.get_contract('currency')

        current_hlc = self.hlc_clock.get_new_hlc_timestamp()
        self.client.raw_driver.soft_apply(hcl=current_hlc)
        self.client.raw_driver.hard_apply_one(hlc=current_hlc)
        self.client.raw_driver.commit()

    def tearDown(self):
        self.client.flush()

    def submit_members(self, constructor_args, owner=None):
        f = open(sync.DEFAULT_PATH + '/genesis/members.s.py')
        self.client.submit(f.read(), name='masternodes', owner=owner, constructor_args=constructor_args)
        f.close()

    def test_init(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        self.assertEqual(mn_contract.current_value(signer='election_house'), [1, 2, 3])

        self.assertEqual(mn_contract.S['yays'], 0)
        self.assertEqual(mn_contract.S['nays'], 0)
        self.assertEqual(mn_contract.S['current_motion'], 0)

    def test_voter_not_masternode_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='assert_vote_is_valid',
                vk='sys',
                action='introduce_motion',
                position=1,
            )

    def test_vote_invalid_action_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='assert_vote_is_valid',
                vk=1,
                action='xxx',
                position=1,
            )

    def test_vote_on_motion_bool_succeeds(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        mn_contract.run_private_function(
            f='assert_vote_is_valid',
            vk=1,
            action='vote_on_motion',
            position=True,
        )

    def test_action_introduce_motion_current_motion_not_no_motion_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        mn_contract.quick_write(variable='S', key='current_motion', value=1)

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='assert_vote_is_valid',
                vk=1,
                action='introduce_motion',
                position=1
            )

    def test_action_introduce_motion_out_of_range_motion_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='assert_vote_is_valid',
                vk=1,
                action='introduce_motion',
                position=10
            )

    def test_action_introduce_motion_no_arg_provided_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='assert_vote_is_valid',
                vk=1,
                action='introduce_motion',
                position=1
            )

    def test_action_introduce_motion_vk_not_str_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='assert_vote_is_valid',
                vk=1,
                action='introduce_motion',
                position=1,
                arg=True
            )

    def test_action_introduce_motion_vk_not_64_chars_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='assert_vote_is_valid',
                vk=1,
                action='introduce_motion',
                position=1,
                arg='a'
            )

    def test_action_introduce_motion_not_valid_hex_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(ValueError):
            mn_contract.run_private_function(
                f='assert_vote_is_valid',
                vk=1,
                action='introduce_motion',
                position=1,
                arg='x' * 64,
                signer='x' * 64
            )

    def test_action_vote_on_motion_fails_if_not_bool(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='assert_vote_is_valid',
                vk=1,
                action='vote_on_motion',
                position=1,
            )

    def test_vote_not_tuple_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 'sys'],
        })

        mn_contract = self.client.get_contract('masternodes')
        with self.assertRaises(AssertionError):
            mn_contract.vote(vk='sys', obj={'hanky': 'panky'})

    def test_vote_1_elem_tuple_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 'sys'],
        })

        mn_contract = self.client.get_contract('masternodes')
        with self.assertRaises(ValueError):
            mn_contract.vote(vk='sys', obj=[1])

    def test_vote_4_elem_tuple_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 'sys'],
        })

        mn_contract = self.client.get_contract('masternodes')
        with self.assertRaises(ValueError):
            mn_contract.vote(vk='sys', obj=[1, 2, 3, 4])

    # ADD_MASTER = 1
    # REMOVE_MASTER = 2
    # ADD_SEAT = 3
    # REMOVE_SEAT = 4

    def test_introduce_motion_remove_seat_fails_if_position_out_of_index(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='introduce_motion',
                position=4,
                arg=None
            )

    def test_introduce_motion_remove_seat_works_and_sets_position_and_motion_opened(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        mn_contract.quick_write('S', 'open_seats', 1)

        env = {'now': Datetime._from_datetime(dt.today() + td(days=7))}

        mn_contract.run_private_function(
            f='introduce_motion',
            position=3,
            arg=None,
            environment=env
        )

        self.assertEqual(mn_contract.quick_read('S', 'current_motion'), 3)
        self.assertEqual(mn_contract.quick_read('S', 'motion_opened'), env['now'])

    def test_add_master_or_remove_master_adds_arg(self):
        self.submit_members(constructor_args={
            'initial_members': ['abc', 'bcd', 'cde'],
        })

        mn_contract = self.client.get_contract('masternodes')

        mn_contract.quick_write('S', 'open_seats', 1)

        env = {'now': Datetime._from_datetime(dt.today() + td(days=7))}

        mn_contract.run_private_function(
            f='introduce_motion',
            position=1,
            arg='abc',
            environment=env
        )

        self.assertEqual(mn_contract.quick_read('S', 'current_motion'), 1)
        self.assertEqual(mn_contract.quick_read('S', 'motion_opened'), env['now'])
        self.assertEqual(mn_contract.quick_read('S', 'member_in_question'), 'abc')

    def test_remove_master_that_does_not_exist_fails(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        with self.assertRaises(AssertionError):
            mn_contract.run_private_function(
                f='introduce_motion',
                position=1,
                arg='abc',
            )

    def test_remove_master_that_exists_passes(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        mn_contract.run_private_function(
            f='introduce_motion',
            position=2,
            arg=1,
        )

    def test_pass_current_motion_add_master_appends_and_removes_seat(self):
        self.contract_driver.driver.set('currency.balances:stu', 100_000)
        # Give joe money
        self.currency.transfer(signer='stu', amount=100_000, to='joe')

        # Joe Allows Spending
        self.currency.approve(signer='joe', amount=100_000, to='elect_members')

        self.elect_members.register(signer='joe')

        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        mn_contract.quick_write('S', 'current_motion', 2)

        mn_contract.run_private_function(
            f='pass_current_motion',
        )

        self.assertEqual(mn_contract.quick_read('S', 'members'), [1, 2, 3, 'joe'])

    def test_pass_current_motion_remove_master_adds_new_seat_and_removes_master(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        mn_contract.quick_write('S', 'member_in_question', 1)
        mn_contract.quick_write('S', 'current_motion', 1)

        mn_contract.run_private_function(
            f='pass_current_motion',
        )

        self.assertEqual(mn_contract.quick_read('S', 'members'), [2, 3])

    def test_pass_remove_seat_removes_least_popular(self):
        self.submit_members(constructor_args={
            'initial_members': ['abc', 'bcd', 'def'],
        }, owner='election_house')

        self.election_house.register_policy(contract='masternodes')
        self.contract_driver.driver.set('currency.balances:stu', 100_000)
        self.currency.approve(signer='stu', amount=100_000, to='elect_members')

        self.elect_members.vote_no_confidence(signer='stu', address='bcd')

        self.election_house.vote(signer='abc', policy='masternodes', value=['introduce_motion', 3])
        self.election_house.vote(signer='bcd', policy='masternodes', value=['vote_on_motion', True])
        self.election_house.vote(signer='def', policy='masternodes', value=['vote_on_motion', True])

        self.assertListEqual(self.election_house.current_value_for_policy(policy='masternodes'), ['abc', 'def'])

    def test_pass_remove_seat_removes_relinquished_first(self):
        self.submit_members(constructor_args={
            'initial_members': ['abc', 'bcd', 'def'],
        }, owner='election_house')
        self.election_house.register_policy(contract='masternodes')

        self.elect_members.relinquish(signer='abc')

        self.election_house.vote(signer='abc', policy='masternodes', value=['introduce_motion', 3])

        self.election_house.vote(signer='bcd', policy='masternodes', value=['vote_on_motion', True])
        self.election_house.vote(signer='def', policy='masternodes', value=['vote_on_motion', True])

        self.assertListEqual(self.election_house.current_value_for_policy(policy='masternodes'), ['bcd', 'def'])

    def test_remove_seat_not_current_masternode_fails(self):
        self.submit_members(constructor_args={
            'initial_members': ['abc', 'bcd', 'def'],
        }, owner='election_house')
        self.election_house.register_policy(contract='masternodes')

        with self.assertRaises(AssertionError):
            self.election_house.vote(signer='abc', policy='masternodes', value=('introduce_motion', 1, 'blah'))

    def test_pass_add_seat_adds_most_popular(self):
        self.contract_driver.driver.set('currency.balances:stu', 100_000)
        # Give joe money
        self.currency.transfer(signer='stu', amount=100_000, to='joe')

        # Joe Allows Spending
        self.currency.approve(signer='joe', amount=100_000, to='elect_members')

        self.elect_members.register(signer='joe')

        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        mn_contract.vote(vk=1, obj=['introduce_motion', 2])

        mn_contract.vote(vk=2, obj=['vote_on_motion', True])
        mn_contract.vote(vk=3, obj=['vote_on_motion', True])

        self.assertListEqual(mn_contract.current_value(), [1, 2, 3, 'joe'])

    def test_current_value_returns_dict(self):
        self.submit_members(constructor_args={
            'initial_members': [1, 2, 3],
        })

        mn_contract = self.client.get_contract('masternodes')

        d = mn_contract.current_value()

        self.assertEqual(d, [1, 2, 3])

    # S['current_motion'] = NO_MOTION
    # S['master_in_question'] = None
    # S['votes'] = 0
    # S.clear('positions')
    # TODO
    #def test_reset_alters_state_correctly(self):
    #    self.submit_members(constructor_args={
    #        'initial_members': [1, 2, 3],
    #    })

    #    mn_contract = self.client.get_contract('masternodes')

    #    mn_contract.quick_write('S', 'current_motion', 1)
    #    mn_contract.quick_write('S', 'member_in_question', 'abc')
    #    mn_contract.quick_write('S', 'yays', 100)
    #    mn_contract.quick_write('S', 'nays', 999)
    #    mn_contract.quick_write(variable='S', key='positions', value=[1, 2, 3, 4], args=['id1'])
    #    mn_contract.quick_write(variable='S', key='positions', value=[1, 2, 3, 4], args=['id2'])
    #    mn_contract.quick_write(variable='S', key='positions', value=[1, 2, 3, 4], args=['id3'])
    #    mn_contract.quick_write(variable='S', key='positions', value=[1, 2, 3, 4], args=['id4'])
    #    mn_contract.quick_write(variable='S', key='positions', value=[1, 2, 3, 4], args=['id5'])
    #    mn_contract.quick_write(variable='S', key='positions', value=[1, 2, 3, 4], args=['id6'])
    #    mn_contract.quick_write(variable='S', key='positions', value=[1, 2, 3, 4], args=['id7'])
    #    mn_contract.quick_write(variable='S', key='positions', value=[1, 2, 3, 4], args=['id8'])

    #    mn_contract.run_private_function(
    #        f='reset',
    #    )

    #    self.assertEqual(mn_contract.quick_read('S', 'current_motion'), 0)
    #    self.assertEqual(mn_contract.quick_read('S', 'member_in_question'), None)
    #    self.assertEqual(mn_contract.quick_read('S', 'yays'), 0)
    #    self.assertEqual(mn_contract.quick_read('S', 'nays'), 0)
    #    self.assertIsNone(mn_contract.quick_read('S', 'positions', args=['id1']))
    #    self.assertIsNone(mn_contract.quick_read('S', 'positions', args=['id2']))
    #    self.assertIsNone(mn_contract.quick_read('S', 'positions', args=['id3']))
    #    self.assertIsNone(mn_contract.quick_read('S', 'positions', args=['id4']))
    #    self.assertIsNone(mn_contract.quick_read('S', 'positions', args=['id5']))
    #    self.assertIsNone(mn_contract.quick_read('S', 'positions', args=['id6']))
    #    self.assertIsNone(mn_contract.quick_read('S', 'positions', args=['id7']))
    #    self.assertIsNone(mn_contract.quick_read('S', 'positions', args=['id8']))

    def test_vote_introduce_motion_affects_state_when_done_properly(self):
        self.submit_members(constructor_args={
            'initial_members': ['a' * 64, 'b' * 64, 'c' * 64],
        })

        mn_contract = self.client.get_contract('masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        mn_contract.vote(vk='a' * 64, obj=['introduce_motion', 3], environment=env)

        self.assertEqual(mn_contract.quick_read('S', 'current_motion'), 3)
        self.assertEqual(mn_contract.quick_read('S', 'motion_opened'), env['now'])

    def test_vote_no_motion_fails(self):
        self.submit_members(constructor_args={
            'initial_members': ['a' * 64, 'b' * 64, 'c' * 64],
        })

        mn_contract = self.client.get_contract('masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        with self.assertRaises(AssertionError):
            mn_contract.vote(vk='a' * 64, obj=('vote_on_motion', False), environment=env)

    def test_vote_on_motion_works(self):
        self.submit_members(constructor_args={
            'initial_members': ['a' * 64, 'b' * 64, 'c' * 64],
        })

        mn_contract = self.client.get_contract('masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        mn_contract.vote(vk='a' * 64, obj=['introduce_motion', 3], environment=env)

        mn_contract.vote(vk='b' * 64, obj=['vote_on_motion', True])

        self.assertEqual(mn_contract.quick_read('S', 'yays'), 1)
        self.assertEqual(mn_contract.quick_read(variable='S', key='positions', args=['b' * 64]), True)

    def test_vote_on_motion_works_nays(self):
        self.submit_members(constructor_args={
            'initial_members': ['a' * 64, 'b' * 64, 'c' * 64],
        })

        mn_contract = self.client.get_contract('masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        mn_contract.vote(vk='a' * 64, obj=['introduce_motion', 3], environment=env)

        mn_contract.vote(vk='b' * 64, obj=['vote_on_motion', False])

        self.assertEqual(mn_contract.quick_read('S', 'nays'), 1)
        self.assertEqual(mn_contract.quick_read('S', 'yays'), 0)
        self.assertEqual(mn_contract.quick_read(variable='S', key='positions', args=['b' * 64]), False)

    def test_vote_on_motion_twice_fails(self):
        self.submit_members(constructor_args={
            'initial_members': ['a' * 64, 'b' * 64, 'c' * 64],
        })

        mn_contract = self.client.get_contract('masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        mn_contract.vote(vk='a' * 64, obj=['introduce_motion', 3], environment=env)

        mn_contract.vote(vk='b' * 64, obj=['vote_on_motion', True])

        with self.assertRaises(AssertionError):
            mn_contract.vote(vk='b' * 64, obj=('vote_on_motion', False))

    def test_vote_reaches_more_than_half_passes(self):
        self.submit_members(constructor_args={
            'initial_members': ['a' * 64, 'b' * 64, 'c' * 64],
        })

        mn_contract = self.client.get_contract('masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        mn_contract.vote(vk='a' * 64, obj=['introduce_motion', 3], environment=env)

        mn_contract.vote(vk='a' * 64, obj=['vote_on_motion', True])
        mn_contract.vote(vk='b' * 64, obj=['vote_on_motion', True])

        self.assertEqual(mn_contract.quick_read('S', 'current_motion'), 0)
        self.assertEqual(mn_contract.quick_read('S', 'member_in_question'), None)
        self.assertEqual(mn_contract.quick_read('S', 'yays'), 0)

    def test_vote_reaches_more_than_half_nays_fails(self):
        self.submit_members(constructor_args={
            'initial_members': ['a' * 64, 'b' * 64, 'c' * 64],
        })

        mn_contract = self.client.get_contract('masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        mn_contract.vote(vk='a' * 64, obj=['introduce_motion', 3], environment=env)

        mn_contract.vote(vk='a' * 64, obj=['vote_on_motion', False])
        mn_contract.vote(vk='b' * 64, obj=['vote_on_motion', False])

        self.assertEqual(mn_contract.quick_read('S', 'current_motion'), 0)
        self.assertEqual(mn_contract.quick_read('S', 'member_in_question'), None)
        self.assertEqual(mn_contract.quick_read('S', 'nays'), 0)

    def test_vote_doesnt_reach_consensus_after_voting_period_fails(self):
        def get_now_from_nanos(add_time: int = 0):
            current_hlc_timestamp = self.hlc_clock.get_new_hlc_timestamp()
            nanos = self.hlc_clock.get_nanos(current_hlc_timestamp)
            nanos = nanos + add_time
            return Datetime._from_datetime(
                dt.utcfromtimestamp(math.ceil(nanos / 1e9))
            )

        self.submit_members(constructor_args={
            'initial_members': ['a' * 64, 'b' * 64, 'c' * 64],
        })

        mn_contract = self.client.get_contract('masternodes')

        env = {'now': get_now_from_nanos()}

        mn_contract.vote(vk='a' * 64, obj=['introduce_motion', 3], environment=env)

        # Vote on the motion
        mn_contract.vote(vk='a' * 64, obj=['vote_on_motion', True], environment=env)

        env = {'now': get_now_from_nanos(add_time=(2 * 86400 * 1000000000))}

        # Voting again will reset the motion
        mn_contract.vote(vk='a' * 64, obj=['vote_on_motion', True], environment=env)

        self.assertEqual(mn_contract.quick_read('S', 'current_motion'), 0)
        self.assertEqual(mn_contract.quick_read('S', 'member_in_question'), None)
        self.assertEqual(mn_contract.quick_read('S', 'nays'), 0)
