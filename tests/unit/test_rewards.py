from unittest import TestCase
from lamden import rewards
from contracting.client import ContractingClient
from lamden.contracts import sync
import lamden

BLOCK = {
            'number': 1,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'stamps_used': 1000,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_1'
                                }
                            }
                        },
                        {
                            'stamps_used': 2000,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_2'
                                }
                            }
                        },
                        {
                            'stamps_used': 3000,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_3'
                                }
                            }
                        }
                    ]
                },

                {
                    'transactions': [
                        {
                            'stamps_used': 4500,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_1'
                                }
                            }
                        },
                        {
                            'stamps_used': 1250,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_1'
                                }
                            }
                        },
                        {
                            'stamps_used': 2750,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_2'
                                }
                            }
                        }
                    ]
                }
            ]
        }

class TestRewards(TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.rewards = rewards.RewardManager()

    def tearDown(self):
        self.client.flush()

    def sync(self):
        sync.setup_genesis_contracts(['stu', 'raghu', 'steve'], ['tejas', 'alex2'], client=self.client)

    def test_contract_exists_false_before_sync(self):
        self.assertFalse(self.rewards.contract_exists('stamp_cost', self.client))

    def test_contract_exists_true_after_sync(self):
        # Sync contracts
        self.sync()
        self.assertTrue(self.rewards.contract_exists('stamp_cost', self.client))

    def test_is_setup_false_before_sync(self):
        self.assertFalse(self.rewards.is_setup(self.client))

    def test_is_setup_true_after_sync(self):
        self.sync()
        self.assertTrue(self.rewards.is_setup(self.client))

    def test_add_to_balance_if_none_sets(self):
        self.rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 123)

    def test_add_to_balance_twice_sets_accordingly(self):
        self.rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 123)

        self.rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 246)

    def test_calculate_rewards_returns_accurate_amounts_per_participant_group(self):
        self.sync()
        self.client.set_var(
            contract='rewards',
            variable='S',
            arguments=['value'],
            value=[0.4, 0.3, 0.1, 0.1, 0.1]
        )

        m, d, f, mapping = self.rewards.calculate_all_rewards(client=self.client, block=BLOCK)

        reconstructed = (m * 3) + (d * 2) + (f * 1) + (f * 1) + (f * 1)

        self.assertAlmostEqual(reconstructed, self.rewards.stamps_in_block(BLOCK))

    def test_calculate_participant_reward_shaves_off_dust(self):
        rounded_reward = self.rewards.calculate_participant_reward(
            participant_ratio=1,
            number_of_participants=1,
            total_stamps_to_split=1.0000000000001
        )

        self.assertEqual(rounded_reward, 1)

    def test_distribute_rewards_adds_to_all_wallets(self):
        self.sync()
        self.client.set_var(
            contract='rewards',
            variable='S',
            arguments=['value'],
            value=[0.4, 0.3, 0.1, 0.1, 0.1]
        )
        self.client.set_var(
            contract='foundation',
            variable='owner',
            value='xxx'
        )

        self.client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=100
        )

        self.client.set_var(
            contract='thing_1',
            variable='__developer__',
            value='stu2'
        )

        self.client.set_var(
            contract='thing_2',
            variable='__developer__',
            value='jeff'
        )

        self.client.set_var(
            contract='thing_3',
            variable='__developer__',
            value='alex'
        )

        total_tau_to_split = 4900

        m, d, f, mapping = self.rewards.calculate_all_rewards(client=self.client, block=BLOCK)

        self.rewards.distribute_rewards(m, d, f, mapping, client=self.client)

        masters = self.client.get_var(contract='masternodes', variable='S', arguments=['members'])
        delegates = self.client.get_var(contract='delegates', variable='S', arguments=['members'])

        for mn in masters:
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[mn], mark=False)
            self.assertEqual(current_balance, m / 100)

        for dl in delegates:
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[dl], mark=False)
            self.assertEqual(current_balance, d / 100)

        current_balance = self.client.get_var(contract='currency', variable='balances', arguments=['xxx'], mark=False)
        self.assertEqual(current_balance, f / 100)

    def test_stamps_in_block(self):
        block = {
            'number': 2,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'stamps_used': 1000
                        },
                        {
                            'stamps_used': 2000
                        },
                        {
                            'stamps_used': 3000
                        }
                    ]
                },

                {
                    'transactions': [
                        {
                            'stamps_used': 4500
                        },
                        {
                            'stamps_used': 1250
                        },
                        {
                            'stamps_used': 2750
                        }
                    ]
                }
            ]
        }

        self.assertEqual(self.rewards.stamps_in_block(block), 14500)

    def test_issue_rewards_full_loop_works(self):
        self.sync()
        self.client.set_var(
            contract='rewards',
            variable='S',
            arguments=['value'],
            value=[0.4, 0.3, 0.1, 0.1, 0.1]
        )
        self.client.set_var(
            contract='foundation',
            variable='owner',
            value='xxx'
        )
        self.client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=100
        )

        self.client.set_var(
            contract='thing_1',
            variable='__developer__',
            value='stu2'
        )

        self.client.set_var(
            contract='thing_2',
            variable='__developer__',
            value='jeff'
        )

        self.client.set_var(
            contract='thing_3',
            variable='__developer__',
            value='alex'
        )

        block = {
            'number': 1,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'stamps_used': 1000,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_1'
                                }
                            }
                        },
                        {
                            'stamps_used': 2000,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_2'
                                }
                            }
                        },
                        {
                            'stamps_used': 3000,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_3'
                                }
                            }
                        }
                    ]
                },

                {
                    'transactions': [
                        {
                            'stamps_used': 4500,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_1'
                                }
                            }
                        },
                        {
                            'stamps_used': 1250,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_1'
                                }
                            }
                        },
                        {
                            'stamps_used': 2750,
                            'transaction': {
                                'payload': {
                                    'contract': 'thing_2'
                                }
                            }
                        }
                    ]
                }
            ]
        }

        # tau to distribute should be 145

        stamps = self.rewards.stamps_in_block(block)

        tau = stamps / 100

        self.assertEqual(tau, 145)

        self.rewards.issue_rewards(block, client=self.client)

        # Stu is owed: 6750 stamps / 100 / 3 =
        # Jeff is owed: 4750 stamps / 100 / 3= 47.5
        # Alex is owed:

        m, d, f, mapping = self.rewards.calculate_all_rewards(client=self.client, block=block)

        masters = self.client.get_var(contract='masternodes', variable='S', arguments=['members'])
        delegates = self.client.get_var(contract='delegates', variable='S', arguments=['members'])

        for mn in masters:
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[mn], mark=False)
            self.assertEqual(current_balance, m / 100)

        for dl in delegates:
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[dl], mark=False)
            self.assertEqual(current_balance, d / 100)

        current_balance = self.client.get_var(contract='currency', variable='balances', arguments=['xxx'], mark=False)
        self.assertEqual(current_balance, f / 100)

        for dev in mapping.keys():
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[dev],
                                                  mark=False)

            self.assertAlmostEqual(current_balance, mapping[dev] / 100)

