from unittest import TestCase
from cilantro_ee.nodes.masternode.block_contender import SubBlockGroup


class TestSubBlockGroup(TestCase):
    def test_init(self):
        SubBlockGroup(0, 'A'*64)
