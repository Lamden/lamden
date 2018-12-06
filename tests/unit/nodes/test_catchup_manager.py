from unittest import TestCase
from unittest.mock import MagicMock

from cilantro.nodes.catchup import CatchupManager
from cilantro.storage.state import StateDriver

from cilantro.messages.block_data.block_data import *
from cilantro.messages.block_data.state_update import *


class TestCatchupManager(TestCase):

    def _build_manager(self, vk='A'*64, store_blocks=True) -> CatchupManager:
        pub, router = MagicMock(), MagicMock()
        return CatchupManager(verifying_key=vk, pub_socket=pub, router_socket=router, store_full_blocks=store_blocks)

    def test_init(self):
        m = self._build_manager()

        self.assertEqual(m.curr_hash, StateDriver.get_latest_block_hash())
        self.assertEqual(m.curr_num, StateDriver.get_latest_block_num())

    def test_recv_block_idx_req(self):
        # TODO implement
        pass

    def test_recv_block_idx_reply(self):
        mn1 = 'ABCD' * 16
        mn2 = 'DCBA' * 16
        mn3 = 'AABB' * 16
        b1 = 'A' * 64
        b2 = 'B' * 64
        b3 = 'C' * 64
        data = [[b1, 1, [mn1,]], [b2, 2, [mn2, mn1]], [b3, 3, [mn1, mn2, mn3]]]

        req = BlockIndexReply(data)

"""
  9 block index request:
 10         - block hash / block num
 11 do we just multicast this to all masternodes? technically all masternodes have this
 12
 13 block index reply:
 14         - list of tuples of form (block hash, block_num, list_of_masternode_vks_who_store_it)
 15 replied on router socket
 16
 17
 18 block_data_request:
 19         - list of block_hashes
 20 sent and received on router socket
 21
 22 block_data_reply:
 23         - list of block_datas
 24 sent and received on router socket"""