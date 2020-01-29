import unittest
from cilantro_ee.core.rewards import RewardManager
from tests import random_txs
from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
from cilantro_ee.contracts import genesis
import os
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.contracts import sync
from contracting.stdlib.bridge.decimal import ContractingDecimal


class TestRewards(unittest.TestCase):
    def test_setup(self):

        self.driver = ContractDriver()
        self.client = ContractingClient()

        genesis_path = os.path.dirname(genesis.__file__)

        with open(os.path.join(genesis_path, 'election_house.s.py')) as f:
            c = f.read()
            self.client.submit(c, name='election_house')

        with open(os.path.join(genesis_path, 'currency.s.py')) as f:
            c = f.read()
            self.client.submit(c, name='currency')

        with open(os.path.join(genesis_path, 'stamp_cost.s.py')) as f:
            c = f.read()
            self.client.submit(c, name='stamp_cost', owner='election_house', constructor_args={'initial_rate': 1_000_000})

        with open(os.path.join(genesis_path, 'rewards.s.py')) as f:
            c = f.read()
            self.client.submit(c, name='rewards', owner='election_house')

        sync.submit_vkbook({'masternodes': ['stu', 'raghu', 'steve'],
          'delegates': ['tejas', 'alex'],
          'masternode_min_quorum': 2,
          'delegate_min_quorum': 3,
          'enable_stamps': True,
          'enable_nonces': True},
         overwrite=True)

        PhoneBook = VKBook()

        self.r = RewardManager(vkbook=PhoneBook)

    def tearDown(self):
        self.driver.flush()

    def test_add_rewards(self):
        block = random_txs.random_block()

        total = 0

        for sb in block.subBlocks:
            for tx in sb.transactions:
                total += tx.stampsUsed

        self.assertEqual(self.r.stamps_in_block(block), total)

    def test_add_to_balance(self):
        currency_contract = self.client.get_contract('currency')
        current_balance = currency_contract.quick_read(variable='balances', key='test') or 0

        self.assertEqual(current_balance, 0)

        self.r.add_to_balance('test', 1234)

        current_balance = currency_contract.quick_read(variable='balances', key='test') or 0

        self.assertEqual(current_balance, 1234)

        self.r.add_to_balance('test', 1000)

        current_balance = currency_contract.quick_read(variable='balances', key='test') or 0

        self.assertEqual(current_balance, 2234)

    def test_stamps_per_tau_works(self):
        self.assertEqual(self.r.stamps_per_tau, 1_000_000)

        stamps = self.client.get_contract('stamp_cost')

        stamps.quick_write('S', 'rate', 555)

        self.assertEqual(self.r.stamps_per_tau, 555)

    def test_pending_rewards_get_sets(self):
        self.assertEqual(self.r.get_pending_rewards(), 0)

        self.r.set_pending_rewards(1000)

        self.assertEqual(self.r.get_pending_rewards(), 1000)

    def test_add_pending_rewards(self):
        block = random_txs.random_block()

        total = 0

        for tx in block.subBlocks[0].transactions:
            total += tx.stampsUsed

        expected = ContractingDecimal(total / 1_000_000)

        self.assertEqual(self.r.get_pending_rewards(), 0)

        self.r.add_pending_rewards(block.subBlocks[0])

        self.assertEqual(self.r.get_pending_rewards(), expected)

    def test_reward_ratio_works(self):
        self.assertEqual(self.r.reward_ratio, [0.5, 0.5, 0, 0])

    def test_issue_rewards_works(self):
        self.r.set_pending_rewards(1000)
        self.r.issue_rewards()

        currency_contract = self.client.get_contract('currency')

        self.r.add_to_balance('raghu', 1000)
        self.r.add_to_balance('steve', 10000)

        self.assertEqual(currency_contract.quick_read(variable='balances', key='stu'), ContractingDecimal(166.66666666666666))
        self.assertEqual(currency_contract.quick_read(variable='balances', key='raghu'), ContractingDecimal(1166.66666666666666))
        self.assertEqual(currency_contract.quick_read(variable='balances', key='steve'), ContractingDecimal(10166.66666666666666))

        self.assertEqual(currency_contract.quick_read(variable='balances', key='tejas'), 250)
        self.assertEqual(currency_contract.quick_read(variable='balances', key='alex'), 250)

        self.assertEqual(self.r.get_pending_rewards(), 0)

if __name__ == '__main__':
    unittest.main()