from unittest import TestCase
from cilantro_ee.core.rewards import RewardManager
from tests import random_txs


class TestRewards(TestCase):
    def test_init(self):
        r = RewardManager()

    def test_add_rewards(self):
        block = random_txs.random_block()

        total = 0

        for sb in block.subBlocks:
            for tx in sb.transactions:
                total += tx.stampsUsed

