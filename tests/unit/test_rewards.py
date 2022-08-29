from unittest import TestCase

from contracting.client import ContractingClient
from contracting.stdlib.bridge.decimal import ContractingDecimal

from lamden import rewards
from lamden.contracts import sync

BLOCK = {
            'number': 1,
            'processed': {
                'stamps_used': 1000,
                'transaction': {
                    'payload': {
                        'contract': 'thing_1'
                    }
                }
            }
        }

class TestRewards(TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.rewards = rewards.RewardManager()

    def tearDown(self):
        self.client.flush()

    def sync(self):
        sync.setup_genesis_contracts(['stu', 'raghu', 'steve'], client=self.client)

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

    def test_METHOD_add_to_balance__returns_proper_balance_update_info(self):
        self.client.set_var('currency', variable='balances', arguments=['stu'], value=100)
        prev_bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        res = self.rewards.add_to_balance('stu', 123, self.client)
        new_bal = self.client.get_var('currency', variable='balances', arguments=['stu'])

        self.assertIsInstance(res.get('key'), str)
        self.assertIsInstance(res.get('value'), ContractingDecimal)
        self.assertIsInstance(res.get('reward'), ContractingDecimal)

        self.assertEqual('currency.balances:stu', res.get('key'))
        self.assertEqual(new_bal, res.get('value'))
        self.assertEqual(new_bal - prev_bal, res.get('reward'))

    def test_METHOD_add_to_balance__set_if_previously_None(self):
        self.rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(123, bal)

    def test_METHOD_add_to_balance__twice_sets_accordingly(self):
        self.rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 123)

        self.rewards.add_to_balance('stu', 123, self.client)
        bal = self.client.get_var('currency', variable='balances', arguments=['stu'])
        self.assertEqual(bal, 246)

    def test_METHOD_calculate_tx_output_rewards__returns_accurate_amounts_per_participant_group(self):
        self.sync()
        self.client.set_var(
            contract='rewards',
            variable='S',
            arguments=['value'],
            value=[0.4, 0.2, 0.1, 0.1, 0.1]
        )

        m, f, developer_mapping = self.rewards.calculate_tx_output_rewards(
            client=self.client,
            contract=BLOCK['processed']['transaction']['payload'].get('contract'),
            total_stamps_to_split=BLOCK['processed'].get('stamps_used')
        )

        self.assertEqual(ContractingDecimal('133.33333333'), m)
        self.assertEqual(ContractingDecimal('100'), f)

        for dev_name, dev_amount in developer_mapping.items():
            self.assertEqual(ContractingDecimal('100'), dev_amount)

    def test_calculate_participant_reward_shaves_off_dust(self):
        rounded_reward = self.rewards.calculate_participant_reward(
            participant_ratio=1,
            number_of_participants=1,
            total_stamps_to_split=1.0000000000001
        )

        self.assertEqual(rounded_reward, 1)

    def test_METHOD_distribute_rewards__adds_to_all_wallets(self):
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

        m, f, developer_mapping = self.rewards.calculate_tx_output_rewards(
            client=self.client,
            contract=BLOCK['processed']['transaction']['payload'].get('contract'),
            total_stamps_to_split=BLOCK['processed'].get('stamps_used')
        )

        self.rewards.distribute_rewards(m, f, developer_mapping, client=self.client)

        masters = self.client.get_var(contract='masternodes', variable='S', arguments=['members'])

        for mn in masters:
            current_balance = self.client.get_var(contract='currency', variable='balances', arguments=[mn], mark=False)
            self.assertEqual(current_balance, m / 100)

        current_balance = self.client.get_var(contract='currency', variable='balances', arguments=['xxx'], mark=False)
        self.assertEqual(current_balance, f / 100)
