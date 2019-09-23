from unittest import TestCase
from cilantro_ee.core.rewards import RewardManager


class TestRewards(TestCase):
    def test_init(self):
        r = RewardManager()