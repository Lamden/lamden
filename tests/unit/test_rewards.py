from unittest import TestCase
from cilantro_ee.core.rewards import RewardManager
from tests import random_txs
from cilantro_ee.storage.state import MetaDataStorage
from contracting.client import ContractingClient
from cilantro_ee.contracts import genesis
import os


class TestRewards(TestCase):
    def setUp(self):

        self.driver = MetaDataStorage()
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

        self.r = RewardManager()

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

        for sb in block.subBlocks:
            for tx in sb.transactions:
                total += tx.stampsUsed

        expected = total / 1_000_000

        self.assertEqual(self.r.get_pending_rewards(), 0)

        self.r.add_pending_rewards(block)

        self.assertEqual(float(self.r.get_pending_rewards()), expected)

    def test_reward_ratio_works(self):
        self.assertEqual(self.r.reward_ratio, [0.5, 0.5, 0, 0])