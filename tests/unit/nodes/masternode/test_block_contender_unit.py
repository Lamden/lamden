from unittest import TestCase
from cilantro_ee.nodes.masternode.block_contender import SubBlockGroup
from cilantro_ee.storage.vkbook import VKBook


class TestSubBlockGroup(TestCase):
    def test_init(self):
        SubBlockGroup(0, 'A'*64)

    def test_consensus_not_reached_after_init(self):
        contacts = VKBook(delegates=['A'*64], masternodes=['A'*64])
        s = SubBlockGroup(0, 'A'*64, contacts=contacts)

        self.assertFalse(s.is_consensus_reached())

