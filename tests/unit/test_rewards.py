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
        pass