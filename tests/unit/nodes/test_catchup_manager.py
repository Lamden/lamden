from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('4-4-4.json')

from unittest import TestCase
from unittest.mock import MagicMock, patch

from cilantro.nodes.catchup import CatchupManager
from cilantro.storage.state import StateDriver
from cilantro.storage.redis import SafeRedis
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.storage.mongo import MDB

from cilantro.messages.block_data.block_data import *
from cilantro.messages.block_data.state_update import *
from cilantro.messages.block_data.block_metadata import *

import asyncio, time
from cilantro.protocol import wallet

SK = 'A' * 64
VK = wallet.get_vk(SK)


class TestCatchupManager(TestCase):

    @classmethod
    def setUpClass(cls):
        MasterOps.init_master(key=SK)

    def setUp(self):
        MDB.reset_db()
        StateDriver.set_latest_block_info(block_hash=GENESIS_BLOCK_HASH, block_num=0)
        # TODO how to rest Mongo between runs?
        self.manager = None
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    def tearDown(self):
        if self.manager.timeout_fut and not self.manager.timeout_fut.done():
            self.manager.timeout_fut.cancel()
        asyncio.get_event_loop().close()

    def _build_manager(self, vk=VK, store_blocks=True) -> CatchupManager:
        pub, router = MagicMock(), MagicMock()
        m = CatchupManager(verifying_key=vk, pub_socket=pub, router_socket=router, store_full_blocks=store_blocks)
        self.manager = m
        return m

    def _assert_router_called_with_msg(self, cm: CatchupManager, msg: MessageBase, possible_headers):
        assert type(possible_headers) in (tuple, bytes), "Header must be a tuple of bytes, or a byte obj"
        for call_arg in cm.router.send_msg.call_args_list:
            args, kwargs = call_arg
            self.assertEqual(args[0], msg)
            if type(possible_headers) is tuple:
                self.assertTrue(kwargs['header'] in possible_headers)
            else:
                self.assertEqual(kwargs['header'], possible_headers)

    def test_init(self):
        m = self._build_manager()

        self.assertEqual(m.curr_hash, StateDriver.get_latest_block_hash())
        self.assertEqual(m.curr_num, StateDriver.get_latest_block_num())

    def test_catchup_with_no_new_blocks(self):
        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]
        vk4 = VKBook.get_masternodes()[3]

        reply_data = None
        index_reply = BlockIndexReply.create(block_info = reply_data)

        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        cm.recv_block_idx_reply(vk1, index_reply)
        self.assertTrue(vk1 in cm.node_idx_reply_set)
        self.assertFalse(cm.is_catchup_done())  # is_catchup_done() should be False, as we've only recv 1/4 required responses

        cm.recv_block_idx_reply(vk2, index_reply)
        cm.recv_block_idx_reply(vk3, index_reply)
        cm.recv_block_idx_reply(vk4, index_reply)

        self.assertTrue(cm.is_catchup_done())  # Now that we have 2/4 replies, we should be out of Catchup

    def test_catchup_with_new_blocks_requests_proper_data(self):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        b1 = 'A' * 64
        b2 = 'B' * 64
        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]

        reply_data1 = [{'blockNum': 1, 'blockHash': b1, 'blockOwners': [vk1, vk2]}]
        reply_data2 = [{'blockNum': 1, 'blockHash': b1, 'blockOwners': [vk1, vk2]},
                       {'blockNum': 2, 'blockHash': b2, 'blockOwners': [vk1, vk2]}]

        index_reply1 = BlockIndexReply.create(reply_data1)
        index_reply2 = BlockIndexReply.create(reply_data2)

        cm.recv_block_idx_reply(vk1, index_reply1)
        cm.recv_block_idx_reply(vk2, index_reply2)
        cm.recv_block_idx_reply(vk3, index_reply2)

        expected_req_1 = BlockDataRequest.create(block_num=1)
        expected_req_2 = BlockDataRequest.create(block_num=2)

        self._assert_router_called_with_msg(cm, msg=expected_req_1, possible_headers=(vk1.encode(), vk2.encode()))
        self._assert_router_called_with_msg(cm, msg=expected_req_2, possible_headers=(vk1.encode(), vk2.encode()))

    def test_recv_block_idx_req_sends_correct_idx_replies_from_block_num(self):
        cm = self._build_manager()
        # cm.run_catchup()
        cm.is_caught_up = True

        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]
        vk4 = VKBook.get_masternodes()[3]

        # Store 5 blocks
        blocks = BlockDataBuilder.create_conseq_blocks(5)
        for block in blocks:
            sblk = StorageDriver.store_block(block.sub_blocks)
            StateDriver.update_with_block(sblk)

        # Send a fake index request from vk1
        req = BlockIndexRequest.create(block_num=0, block_hash='0' * 64)
        cm.recv_block_idx_req(vk1, req)

        # Assert we sent out the expected reply over Router
        all_idx_replies = []
        for block in reversed(blocks):
            all_idx_replies.append({'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': [vk1, vk2, vk3, vk4]})
        expected_reply = BlockIndexReply.create(all_idx_replies)

        print(expected_reply)
        print(cm.router.send_msg.call_args)
        self._assert_router_called_with_msg(cm, msg=expected_reply, possible_headers=(vk1.encode(),))
        cm.is_caught_up = False

    def test_catchup_with_new_blocks_and_replies(self):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(5)

        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]
        vk4 = VKBook.get_masternodes()[3]

        all_idx_replies = []
        reply_datas = []
        for block in blocks:
            all_idx_replies.append({'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': [vk1, vk2]})
            reply_datas.append(BlockDataReply.create_from_block(block))

        # Send the BlockIndexReplies (1 extra)
        reply_data1 = all_idx_replies[:2]  # this incomplete reply only includes the first 2 blocks
        reply_data2 = all_idx_replies
        reply_data3 = all_idx_replies[:4]
        index_reply1 = BlockIndexReply.create(reply_data1)
        index_reply2 = BlockIndexReply.create(reply_data2)
        index_reply3 = BlockIndexReply.create(reply_data3)
        cm.recv_block_idx_reply(vk1, index_reply1)  # only first 2/5
        cm.recv_block_idx_reply(vk4, index_reply3)  # first 4/5
        cm.recv_block_idx_reply(vk3, index_reply2)  # 5/5
        cm.recv_block_idx_reply(vk2, index_reply2)  # 5/5

        self.assertFalse(cm.is_catchup_done())

        # Send the BlockDataReplies
        for bd_reply in reply_datas:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

        # Assert we set curr_hash and curr_num to the last added block
        # self.assertEqual(cm.curr_hash, blocks[-1].block_hash)
        self.assertEqual(cm.curr_num, blocks[-1].block_num)

        # Assert Redis has been updated
        self.assertEqual(StateDriver.get_latest_block_num(), blocks[-1].block_num)
        self.assertEqual(StateDriver.get_latest_block_hash(), blocks[-1].block_hash)

        # Assert Mongo has been updated
        self.assertEqual(StorageDriver.get_latest_block_num(), blocks[-1].block_num)
        self.assertEqual(StorageDriver.get_latest_block_hash(), blocks[-1].block_hash)

    def test_catchup_with_new_blocks_and_replies_when_we_start_with_some_blocks_already(self):
        blocks = BlockDataBuilder.create_conseq_blocks(5)

        # Store the first 2 blocks
        curr_blk = blocks[1]
        StateDriver.set_latest_block_info(block_hash=curr_blk.block_hash, block_num=curr_blk.block_num)

        cm = self._build_manager(store_blocks=False)

        print("catchup man curr num {}".format(cm.curr_num))

        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]
        vk4 = VKBook.get_masternodes()[3]

        all_idx_replies = []
        reply_datas = []
        for block in blocks:
            all_idx_replies.append({'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': [vk1, vk2]})
            reply_datas.append(BlockDataReply.create_from_block(block))

        # Send the BlockIndexReplies (1 extra)
        reply_data1 = all_idx_replies[:2]  # this incomplete reply only includes the first 2 blocks
        reply_data2 = all_idx_replies
        reply_data3 = all_idx_replies[:4]
        index_reply1 = BlockIndexReply.create(reply_data1)
        index_reply2 = BlockIndexReply.create(reply_data2)
        index_reply3 = BlockIndexReply.create(reply_data3)
        cm.recv_block_idx_reply(vk1, index_reply1)  # only first 2/5
        cm.recv_block_idx_reply(vk3, index_reply2)  # 5/5

        cm.recv_block_idx_reply(vk4, index_reply3)  # first 4/5
        cm.recv_block_idx_reply(vk2, index_reply2)  # 5/5

        print('target num {}'.format(cm.target_blk_num))
        print('curr num {}'.format(cm.curr_num))
        print('is_catchup_done {}'.format(cm.is_catchup_done()))
        print('is caught up {}'.format(cm.is_caught_up))

        print("all idx replies:\n{}".format(all_idx_replies))

        self.assertFalse(cm.is_caught_up)
        self.assertFalse(cm.is_catchup_done())

        # Send the BlockDataReplies
        for bd_reply in reply_datas:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

        # Assert we set curr_hash and curr_num to the last added block
        self.assertEqual(cm.curr_hash, blocks[-1].block_hash)
        self.assertEqual(cm.curr_num, blocks[-1].block_num)

        # Assert Redis has been updated
        self.assertEqual(StateDriver.get_latest_block_num(), blocks[-1].block_num)
        self.assertEqual(StateDriver.get_latest_block_hash(), blocks[-1].block_hash)

    def test_get_new_block_notif_many_behind_after_caught_up(self):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(8)

        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]
        vk4 = VKBook.get_masternodes()[3]

        all_idx_replies = []
        reply_datas = []
        for block in blocks[:5]:
            all_idx_replies.append({'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': [vk1, vk2]})
            reply_datas.append(BlockDataReply.create_from_block(block))

        # Send the BlockIndexReplies (1 extra)
        reply_data1 = all_idx_replies[:2]  # this incomplete reply only includes the first 2 blocks
        reply_data2 = all_idx_replies
        reply_data3 = all_idx_replies[:4]
        index_reply1 = BlockIndexReply.create(reply_data1)
        index_reply2 = BlockIndexReply.create(reply_data2)
        index_reply3 = BlockIndexReply.create(reply_data3)
        cm.recv_block_idx_reply(vk1, index_reply1)
        cm.recv_block_idx_reply(vk2, index_reply2)
        cm.recv_block_idx_reply(vk3, index_reply3)
        cm.recv_block_idx_reply(vk4, index_reply3)

        # Send the BlockDataReplies
        for bd_reply in reply_datas:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

        # Now, send a NewBlockNotification from a new hash/num, and make sure things worked propperly
        new_blocks = blocks[5:]
        new_block_notif = NewBlockNotification.create_from_block_data(new_blocks[-1])

        cm.recv_new_blk_notif(new_block_notif)
        self.assertFalse(cm.is_catchup_done())

    def test_get_new_block_notif_one_behind_after_caught_up(self):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(6)

        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]
        vk4 = VKBook.get_masternodes()[3]

        all_idx_replies = []
        reply_datas = []
        for block in blocks[:5]:
            all_idx_replies.append({'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': [vk1, vk2]})
            reply_datas.append(BlockDataReply.create_from_block(block))

        # Send the BlockIndexReplies (1 extra)
        reply_data1 = all_idx_replies[:2]  # this incomplete reply only includes the first 2 blocks
        reply_data2 = all_idx_replies
        reply_data3 = all_idx_replies[:4]
        index_reply1 = BlockIndexReply.create(reply_data1)
        index_reply2 = BlockIndexReply.create(reply_data2)
        index_reply3 = BlockIndexReply.create(reply_data3)
        cm.recv_block_idx_reply(vk1, index_reply1)
        cm.recv_block_idx_reply(vk2, index_reply2)
        cm.recv_block_idx_reply(vk3, index_reply3)
        cm.recv_block_idx_reply(vk4, index_reply3)

        # Send the BlockDataReplies
        for bd_reply in reply_datas:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

        # Now, send a NewBlockNotification from a new hash/num, and make sure things worked propperly
        new_block_notif = NewBlockNotification.create_from_block_data(blocks[-1])

        cm.recv_new_blk_notif(new_block_notif)
        self.assertFalse(cm.is_catchup_done())

    def test_catchup_qourum_reached_for_mn(self):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(6)

        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]
        vk4 = VKBook.get_masternodes()[3]

        all_idx_replies = []
        reply_datas = []
        for block in blocks[:5]:
            all_idx_replies.append({'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': [vk1, vk2]})
            reply_datas.append(BlockDataReply.create_from_block(block))

        index_reply1 = BlockIndexReply.create(all_idx_replies[:2])
        index_reply2 = BlockIndexReply.create(all_idx_replies)
        index_reply3 = BlockIndexReply.create(all_idx_replies[:4])

        # As a Masternode (store_full_blocks=True), he should require 2/4 other idx replies
        cm.recv_block_idx_reply(vk1, index_reply1)
        self.assertFalse(cm._check_idx_reply_quorum())

        cm.recv_block_idx_reply(vk2, index_reply2)
        self.assertTrue(cm._check_idx_reply_quorum())

        cm.recv_block_idx_reply(vk3, index_reply3)
        self.assertTrue(cm._check_idx_reply_quorum())

        cm.recv_block_idx_reply(vk4, index_reply3)
        self.assertTrue(cm._check_idx_reply_quorum())

    # TODO @raghu, i think this test needs to be fixed
    def test_catchup_qourum_reached_for_delegate(self):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(6)

        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]
        vk4 = VKBook.get_masternodes()[3]

        all_idx_replies = []
        reply_datas = []
        for block in blocks[:5]:
            all_idx_replies.append({'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': [vk1, vk2]})
            reply_datas.append(BlockDataReply.create_from_block(block))

        index_reply1 = BlockIndexReply.create(all_idx_replies[:2])
        index_reply2 = BlockIndexReply.create(all_idx_replies)
        index_reply3 = BlockIndexReply.create(all_idx_replies[:4])

        # As a Delegate (store_full_blocks=False), he should require 3/4 other idx replies
        cm.recv_block_idx_reply(vk1, index_reply1)
        self.assertFalse(cm._check_idx_reply_quorum())

        cm.recv_block_idx_reply(vk2, index_reply2)
        self.assertFalse(cm._check_idx_reply_quorum())

        cm.recv_block_idx_reply(vk3, index_reply3)
        self.assertTrue(cm._check_idx_reply_quorum())

        cm.recv_block_idx_reply(vk4, index_reply3)
        self.assertTrue(cm._check_idx_reply_quorum())

    def test_catchup_with_new_blocks_and_replies_when_we_start_with_some_blocks_already_and_then_we_catchup_again(self):
        """ In this test, there are 8 blocks
        - we start CM at block 2
        - catchup him up to block 5
        - then, catch him up to block 9 """
        blocks = BlockDataBuilder.create_conseq_blocks(8)

        # Store the first 2 blocks
        curr_blk = blocks[1]
        StateDriver.set_latest_block_info(block_hash=curr_blk.block_hash, block_num=curr_blk.block_num)

        cm = self._build_manager(store_blocks=False)

        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        vk1 = VKBook.get_masternodes()[0]
        vk2 = VKBook.get_masternodes()[1]
        vk3 = VKBook.get_masternodes()[2]
        vk4 = VKBook.get_masternodes()[3]

        all_idx_replies = []
        reply_datas = []
        for block in blocks:
            all_idx_replies.append({'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': [vk1, vk2]})
            reply_datas.append(BlockDataReply.create_from_block(block))

        first_round_idxs = all_idx_replies[:5]
        first_round_blocks = blocks[:5]
        first_round_data = reply_datas[:5]
        second_round_idxs = all_idx_replies[5:]
        second_round_blocks = blocks[5:]
        second_round_data = reply_datas[5:]

        index_reply1 = BlockIndexReply.create(first_round_idxs[:2])
        index_reply2 = BlockIndexReply.create(first_round_idxs)
        index_reply3 = BlockIndexReply.create(first_round_idxs[:4])

        # START OF FIRST ROUND, we catchup to 5 new blocks

        cm.recv_block_idx_reply(vk1, index_reply1)  # only first 2/5
        cm.recv_block_idx_reply(vk3, index_reply2)  # 5/5
        cm.recv_block_idx_reply(vk4, index_reply3)  # first 4/5
        cm.recv_block_idx_reply(vk2, index_reply2)  # 5/5

        self.assertFalse(cm.is_caught_up)
        self.assertFalse(cm.is_catchup_done())

        # Send the BlockDataReplies (round 1)
        for bd_reply in first_round_data:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

        # Assert we set curr_hash and curr_num to the last added block
        self.assertEqual(cm.curr_hash, first_round_blocks[-1].block_hash)
        self.assertEqual(cm.curr_num, first_round_blocks[-1].block_num)

        # Assert Redis has been updated
        self.assertEqual(StateDriver.get_latest_block_num(), first_round_blocks[-1].block_num)
        self.assertEqual(StateDriver.get_latest_block_hash(), first_round_blocks[-1].block_hash)

        # START OF SECOND ROUND, we catchup to 3 new blocks

        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        index_reply1 = BlockIndexReply.create(second_round_idxs[:2])
        index_reply2 = BlockIndexReply.create(second_round_idxs)
        index_reply3 = BlockIndexReply.create(second_round_idxs[:4])
        cm.recv_block_idx_reply(vk1, index_reply1)
        cm.recv_block_idx_reply(vk3, index_reply2)
        cm.recv_block_idx_reply(vk4, index_reply3)
        cm.recv_block_idx_reply(vk2, index_reply2)

        self.assertFalse(cm.is_caught_up)
        self.assertFalse(cm.is_catchup_done())

        # Send the BlockDataReplies (round 2)
        for bd_reply in second_round_data:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

        # Assert we set curr_hash and curr_num to the last added block
        self.assertEqual(cm.curr_hash, second_round_blocks[-1].block_hash)
        self.assertEqual(cm.curr_num, second_round_blocks[-1].block_num)

        # Assert Redis has been updated
        self.assertEqual(StateDriver.get_latest_block_num(), second_round_blocks[-1].block_num)
        self.assertEqual(StateDriver.get_latest_block_hash(), second_round_blocks[-1].block_hash)




if __name__ == "__main__":
    import unittest
    unittest.main()

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
