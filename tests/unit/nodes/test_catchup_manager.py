from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')

from unittest import TestCase
from unittest.mock import MagicMock, patch

from cilantro.nodes.catchup import CatchupManager
from cilantro.storage.state import StateDriver

from cilantro.messages.block_data.block_data import *
from cilantro.messages.block_data.state_update import *

import asyncio
from cilantro.storage.redis import SafeRedis


class TestCatchupManager(TestCase):

    def setUp(self):
        SafeRedis.flushall()
        self.manager = None

    def tearDown(self):
        if self.manager.timeout_fut and not self.manager.timeout_fut.done():
            self.manager.timeout_fut.cancel()
        asyncio.get_event_loop().close()

    def _build_manager(self, vk='A'*64, store_blocks=True) -> CatchupManager:
        pub, router = MagicMock(), MagicMock()
        m = CatchupManager(verifying_key=vk, pub_socket=pub, router_socket=router, store_full_blocks=store_blocks)
        self.manager = m
        return m

    def test_init(self):
        m = self._build_manager()

        self.assertEqual(m.curr_hash, StateDriver.get_latest_block_hash())
        self.assertEqual(m.curr_num, StateDriver.get_latest_block_num())

    # def test_catchup_with_no_new_blocks(self):
    #     cm = self._build_manager()
    #
    #     cm.run_catchup()
    #
    #     self.assertTrue(cm.catchup_state)
    #
    #     reply_data = [{'blockHash': GENESIS_BLOCK_HASH,
    #                    'blockOwners': [VKBook.get_masternodes()[0], VKBook.get_masternodes()[1]], 'blockNum': 0}, ]
    #     index_reply = BlockIndexReply.create(reply_data)
    #
    #     cm.recv_block_idx_reply(VKBook.get_masternodes()[0], index_reply)
    #     cm.recv_block_idx_reply(VKBook.get_masternodes()[1], index_reply)
    #
    #     self.assertFalse(cm.catchup_state)

    def test_catchup_with_new_blocks(self):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertTrue(cm.catchup_state)

        b1 = 'A' * 64
        b2 = 'B' * 64
        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]

        reply_data1 = [{'blockHash': b1, 'blockOwners': [vk1, vk2], 'blockNum': 1},
                       {'blockHash': b2, 'blockOwners': [vk1, vk2], 'blockNum': 2}]
        reply_data2 = [{'blockHash': b1, 'blockOwners': [vk1, vk2], 'blockNum': 1},
                       {'blockHash': b2, 'blockOwners': [vk1, vk2], 'blockNum': 2}]

        index_reply1 = BlockIndexReply.create(reply_data1)
        index_reply2 = BlockIndexReply.create(reply_data2)

        cm.recv_block_idx_reply(vk1, index_reply1)
        self.assertFalse(cm.catchup_state)

        cm.recv_block_idx_reply(vk2, index_reply1)
        self.assertTrue(cm.catchup_state)

    def test_catchup_with_no_new_blocks(self):
        cm = self._build_manager()

        cm.run_catchup()

        self.assertTrue(cm.catchup_state)

        reply_data = []
        index_reply = BlockIndexReply.create(reply_data)

        # We should still be in catchup until we achieve consensus on IndexReplies
        cm.recv_block_idx_reply(VKBook.get_masternodes()[0], index_reply)
        self.assertTrue(cm.catchup_state)

        # Now that we have 2/2 replies, we should be out of Catchup
        cm.recv_block_idx_reply(VKBook.get_masternodes()[1], index_reply)
        self.assertFalse(cm.catchup_state)

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