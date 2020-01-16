from deprecated.test import set_testnet_config
set_testnet_config('4-4-4.json')

from unittest import TestCase
from unittest.mock import MagicMock

from cilantro_ee.nodes.catchup import CatchupManager
from cilantro_ee.services.storage.state import MetaDataStorage

from cilantro_ee.messages.block_data.block_data import *
from cilantro_ee.messages.block_data.state_update import *
import asyncio, time
from cilantro_ee.core.crypto import wallet

from cilantro_ee.services.storage.vkbook import VKBook

SK = 'A' * 64
VK = wallet.get_vk(SK)

MN_SK1 = 'B' * 64
MN_VK1 = wallet.get_vk(MN_SK1)
MN_SK2 = 'C' * 64
MN_VK2 = wallet.get_vk(MN_SK2)
MN_SK3 = 'D' * 64
MN_VK3 = wallet.get_vk(MN_SK3)
MN_SK4 = 'E' * 64
MN_VK4 = wallet.get_vk(MN_SK4)

MN_VKS = [MN_VK1, MN_VK2, MN_VK3, MN_VK4]

DELE_SK1 = '1' * 64
DELE_VK1 = wallet.get_vk(DELE_SK1)
DELE_SK2 = '2' * 64
DELE_VK2 = wallet.get_vk(DELE_SK2)
DELE_SK3 = '3' * 64
DELE_VK3 = wallet.get_vk(DELE_SK3)
DELE_SK4 = '4' * 64
DELE_VK4 = wallet.get_vk(DELE_SK4)

DELE_VKS = [DELE_VK1, DELE_VK2, DELE_VK3, DELE_VK4]

PhoneBook = VKBook(MN_VKS, DELE_VKS, len(MN_VKS), len(DELE_VKS), False, False, debug=True)


class TestCatchupManager(TestCase):
    def setUp(self):
        self.state = MetaDataStorage()

        self.state.latest_block_hash = GENESIS_BLOCK_HASH
        self.state.latest_block_num = 0
        # TODO how to reset Mongo between runs?
        self.manager = None
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    def tearDown(self):
        #if self.manager.timeout_fut and not self.manager.timeout_fut.done():
        #    self.manager.timeout_fut.cancel()
        asyncio.get_event_loop().close()

    def _build_manager(self, vk=VK, store_blocks=True) -> CatchupManager:
        pub, router = MagicMock(), MagicMock()
        m = CatchupManager(verifying_key=MN_VK1, signing_key=MN_SK1, pub_socket=pub, router_socket=router, store_full_blocks=store_blocks)
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

        self.assertEqual(m.curr_hash, self.state.get_latest_block_hash())
        self.assertEqual(m.curr_num, self.state.get_latest_block_num())

    def test_catchup_with_no_new_blocks(self, *args):
        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]
        MN_VK4 = PhoneBook.masternodes[3]

        vks = [MN_VK1, MN_VK2, MN_VK3, MN_VK4]

        reply_data = None
        index_reply = BlockIndexReply.create(block_info = reply_data)

        cm = self._build_manager()
        cm.run_catchup()

        my_quorum = cm.my_quorum
        while (my_quorum > 0) and (len(vks) > 0):
            self.assertFalse(cm.is_catchup_done())
            cm.recv_block_idx_reply(vks.pop(), index_reply)
            my_quorum -= 1

        self.assertTrue(cm.is_catchup_done())  # Now that we have quorum replies, we should be out of Catchup

    def test_catchup_with_new_blocks_requests_proper_data(self, *args):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        b1 = 'A' * 64
        b2 = 'B' * 64
        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]

        reply_data1 = [{'blockNum': 1, 'blockHash': b1, 'blockOwners': [MN_VK1, MN_VK2]}]
        reply_data2 = [{'blockNum': 2, 'blockHash': b2, 'blockOwners': [MN_VK1, MN_VK2]},
                       {'blockNum': 1, 'blockHash': b1, 'blockOwners': [MN_VK1, MN_VK2]}]
        reply_data3 = [{'blockNum': 2, 'blockHash': b2, 'blockOwners': [MN_VK1, MN_VK2]},
                       {'blockNum': 1, 'blockHash': b1, 'blockOwners': [MN_VK1, MN_VK2]}]

        index_reply1 = BlockIndexReply.create(reply_data1)
        index_reply2 = BlockIndexReply.create(reply_data2)
        index_reply3 = BlockIndexReply.create(reply_data3)


        cm.recv_block_idx_reply(MN_VK1, index_reply1)
        cm.recv_block_idx_reply(MN_VK2, index_reply2)
        cm.recv_block_idx_reply(MN_VK3, index_reply3)

        expected_req_1 = BlockDataRequest.create(block_num=1)
        expected_req_2 = BlockDataRequest.create(block_num=2)

        self._assert_router_called_with_msg(cm, msg=expected_req_1, possible_headers=(MN_VK1.encode(), MN_VK2.encode()))
        self._assert_router_called_with_msg(cm, msg=expected_req_2, possible_headers=(MN_VK1.encode(), MN_VK2.encode()))

    def test_recv_block_idx_req_sends_correct_idx_replies_from_block_num(self, *args):
        cm = self._build_manager()
        # cm.run_catchup()
        cm.is_caught_up = True

        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]
        MN_VK4 = PhoneBook.masternodes[3]

        # Store 5 blocks
        blocks = BlockDataBuilder.create_conseq_blocks(5)
        for block in blocks:
            # sblk = self.state.store_block(block.sub_blocks)
            self.state.update_with_block(block)

        # Send a fake index request from MN_VK1
        req = BlockIndexRequest.create(block_num=0, block_hash='0' * 64)
        cm.recv_block_idx_req(MN_VK1, req)

        # Assert we sent out the expected reply over Router
        all_idx_replies = []
        for block in reversed(blocks):
            all_idx_replies.append({'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': [MN_VK1, MN_VK2, MN_VK3, MN_VK4]})
        expected_reply = BlockIndexReply.create(all_idx_replies)

        print(expected_reply)
        print(cm.router.send_msg.call_args)
        self._assert_router_called_with_msg(cm, msg=expected_reply, possible_headers=(MN_VK1.encode(),))
        cm.is_caught_up = False

    def test_catchup_with_new_blocks_and_replies(self, *args):
        cm = self._build_manager(store_blocks=False)
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(5)

        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]
        MN_VK4 = PhoneBook.masternodes[3]

        all_idx_replies = ()
        reply_datas = []
        for block in blocks:
            all_idx_replies = ({'blockNum': block.block_num, 'blockHash': block.block_hash,
                                'blockOwners': [MN_VK1, MN_VK2]},) + all_idx_replies
            reply_datas.append(BlockDataReply.create_from_block(block))

        index_reply1 = BlockIndexReply.create(list(all_idx_replies[2:]))
        index_reply2 = BlockIndexReply.create(list(all_idx_replies))
        index_reply3 = BlockIndexReply.create(list(all_idx_replies[4:]))
        index_reply4 = BlockIndexReply.create(list(all_idx_replies))

        cm.recv_block_idx_reply(MN_VK1, index_reply1)  # only first 2/5
        cm.recv_block_idx_reply(MN_VK4, index_reply3)  # first 4/5
        cm.recv_block_idx_reply(MN_VK3, index_reply2)  # 5/5
        cm.recv_block_idx_reply(MN_VK2, index_reply4)  # 5/5

        self.assertFalse(cm.is_catchup_done())

        # Send the BlockDataReplies
        for bd_reply in reply_datas:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

        # Assert we set curr_hash and curr_num to the last added block
        # self.assertEqual(cm.curr_hash, blocks[-1].block_hash)
        self.assertEqual(cm.curr_num, blocks[-1].block_num)

        # Assert Redis has been updated
        self.assertEqual(self.state.get_latest_block_num(), blocks[-1].block_num)
        self.assertEqual(self.state.get_latest_block_hash(), blocks[-1].block_hash)

        # Assert Mongo has been updated
        self.assertEqual(self.state.get_latest_block_num(), blocks[-1].block_num)
        self.assertEqual(self.state.get_latest_block_hash(), blocks[-1].block_hash)

    def test_catchup_with_new_blocks_and_replies_when_we_start_with_some_blocks_already(self, *args):
        blocks = BlockDataBuilder.create_conseq_blocks(5)

        # Store the first 2 blocks
        curr_blk = blocks[1]
        self.state.set_latest_block_hash(curr_blk.block_hash)
        self.state.set_latest_block_num(curr_blk.block_num)

        cm = self._build_manager(store_blocks=False)

        print("catchup man curr num {}".format(cm.curr_num))

        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]
        MN_VK4 = PhoneBook.masternodes[3]

        all_idx_replies = ()
        reply_datas = []
        for block in blocks:
            all_idx_replies = ({'blockNum': block.block_num, 'blockHash': block.block_hash,
                                'blockOwners': [MN_VK1, MN_VK2]},) + all_idx_replies
            reply_datas.append(BlockDataReply.create_from_block(block))

        # Send the BlockIndexReplies (1 extra)
        index_reply1 = BlockIndexReply.create(list(all_idx_replies[2:]))
        index_reply2 = BlockIndexReply.create(list(all_idx_replies))
        index_reply3 = BlockIndexReply.create(list(all_idx_replies[4:]))
        index_reply4 = BlockIndexReply.create(list(all_idx_replies))


        cm.recv_block_idx_reply(MN_VK1, index_reply1)  # only first 2/5
        cm.recv_block_idx_reply(MN_VK3, index_reply2)  # 5/5

        cm.recv_block_idx_reply(MN_VK4, index_reply3)  # first 4/5
        cm.recv_block_idx_reply(MN_VK2, index_reply4)  # 5/5

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
        self.assertEqual(self.state.get_latest_block_num(), blocks[-1].block_num)
        self.assertEqual(self.state.get_latest_block_hash(), blocks[-1].block_hash)

    def test_get_new_block_notif_many_behind_after_caught_up(self, *args):
        cm = self._build_manager(store_blocks=False)
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(6)

        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]
        MN_VK4 = PhoneBook.masternodes[3]

        all_idx_replies = ()
        reply_datas = []
        for block in blocks[:5]:
            all_idx_replies = ({'blockNum': block.block_num, 'blockHash': block.block_hash,
                                'blockOwners': [MN_VK1, MN_VK2]},) + all_idx_replies
            reply_datas.append(BlockDataReply.create_from_block(block))

        # Send the BlockIndexReplies (1 extra)

        index_reply1 = BlockIndexReply.create(list(all_idx_replies))
        index_reply2 = BlockIndexReply.create(list(all_idx_replies))
        index_reply3 = BlockIndexReply.create(list(all_idx_replies))
        index_reply4 = BlockIndexReply.create(list(all_idx_replies))


        cm.recv_block_idx_reply(MN_VK1, index_reply1)
        cm.recv_block_idx_reply(MN_VK2, index_reply2)
        cm.recv_block_idx_reply(MN_VK3, index_reply3)
        cm.recv_block_idx_reply(MN_VK4, index_reply4)

        self.assertFalse(cm.is_catchup_done())

        # Send the BlockDataReplies
        for bd_reply in reply_datas[:3]:
            cm.recv_block_data_reply(bd_reply)

        self.assertFalse(cm.is_catchup_done())

        # Now, send a NewBlockNotification from a new hash/num, and make sure things worked propperly
        blk = blocks[-1]
        new_block_notif = NewBlockNotification.create(blk.prev_block_hash, blk.block_hash, blk.block_num,
                                                      0, blk.block_owners, blk.input_hashes)
        cm.recv_new_blk_notif(new_block_notif)

        self.assertFalse(cm.is_catchup_done())

        reply_datas.append(BlockDataReply.create_from_block(blocks[-1]))

        # Send the BlockDataReplies
        for bd_reply in reply_datas[3:]:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

        # # Assert Redis has been updated
        self.assertEqual(self.state.get_latest_block_num(), blocks[-1].block_num)
        self.assertEqual(self.state.get_latest_block_hash(), blocks[-1].block_hash)

    def test_get_new_block_notif_one_behind_after_caught_up(self, *args):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(6)

        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]
        MN_VK4 = PhoneBook.masternodes[3]

        all_idx_replies = ()
        reply_datas = []
        for block in blocks[:5]:
            all_idx_replies = ({'blockNum': block.block_num, 'blockHash': block.block_hash,
                                'blockOwners': [MN_VK1, MN_VK2]},) + all_idx_replies
            reply_datas.append(BlockDataReply.create_from_block(block))

        # Send the BlockIndexReplies (1 extra)

        index_reply1 = BlockIndexReply.create(list(all_idx_replies[2:]))
        index_reply2 = BlockIndexReply.create(list(all_idx_replies))
        index_reply3 = BlockIndexReply.create(list(all_idx_replies[4:]))
        index_reply4 = BlockIndexReply.create(list(all_idx_replies))

        cm.recv_block_idx_reply(MN_VK1, index_reply1)
        cm.recv_block_idx_reply(MN_VK2, index_reply2)
        cm.recv_block_idx_reply(MN_VK3, index_reply3)
        cm.recv_block_idx_reply(MN_VK4, index_reply4)

        # Send the BlockDataReplies
        for bd_reply in reply_datas:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

        # Now, send a NewBlockNotification from a new hash/num, and make sure things worked propperly
        blk = blocks[-1]
        new_block_notif = NewBlockNotification.create(blk.prev_block_hash, blk.block_hash, blk.block_num,
                                                      0, blk.block_owners, blk.input_hashes)

        cm.recv_new_blk_notif(new_block_notif)
        self.assertFalse(cm.is_catchup_done())

    def test_catchup_qourum_reached_for_mn(self, *args):
        cm = self._build_manager()
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(6)

        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]
        MN_VK4 = PhoneBook.masternodes[3]

        all_idx_replies = ()
        reply_datas = []
        for block in reversed(blocks[:5]):
            all_idx_replies = all_idx_replies + ({'blockNum': block.block_num, 'blockHash': block.block_hash,
                                                  'blockOwners': [MN_VK1, MN_VK2]},)
            reply_datas.append(BlockDataReply.create_from_block(block))

        index_reply1 = BlockIndexReply.create(list(all_idx_replies[2:]))
        index_reply2 = BlockIndexReply.create(list(all_idx_replies))
        index_reply3 = BlockIndexReply.create(list(all_idx_replies[4:]))
        index_reply4 = BlockIndexReply.create(list(all_idx_replies[4:]))

        vks = [MN_VK4, MN_VK3, MN_VK2, MN_VK1]
        idx_replies = [index_reply4, index_reply3, index_reply2, index_reply1]

        my_quorum = cm.my_quorum
        self.assertTrue(my_quorum > 0)

        while (my_quorum > 0) and (len(vks) > 0):
            self.assertFalse(cm.is_catchup_done())
            cm.recv_block_idx_reply(vks.pop(), idx_replies.pop())
            my_quorum -= 1

        self.assertTrue(cm.is_catchup_done())  # Now that we have quorum replies, we should be out of Catchup

    def test_catchup_qourum_reached_for_delegate(self, *args):
        cm = self._build_manager(store_blocks=False)
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        blocks = BlockDataBuilder.create_conseq_blocks(6)

        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]
        MN_VK4 = PhoneBook.masternodes[3]

        all_idx_replies = ()
        reply_datas = []
        for block in reversed(blocks):
            all_idx_replies = all_idx_replies + ({'blockNum': block.block_num, 'blockHash': block.block_hash,
                                                  'blockOwners': [MN_VK1, MN_VK2]},)
            reply_datas.append(BlockDataReply.create_from_block(block))


        index_reply1 = BlockIndexReply.create(list(all_idx_replies[4:]))
        index_reply2 = BlockIndexReply.create(list(all_idx_replies))
        index_reply3 = BlockIndexReply.create(list(all_idx_replies[2:]))
        index_reply4 = BlockIndexReply.create(list(all_idx_replies))


        my_quorum = cm.my_quorum
        self.assertTrue(my_quorum > 0)
        # As a Delegate (store_full_blocks=False), he should require 2/3 other idx replies
        #
        cm.recv_block_idx_reply(MN_VK1, index_reply1)
        my_quorum -= 1
        is_quorum = not cm._check_idx_reply_quorum() if my_quorum > 0 else cm._check_idx_reply_quorum()
        self.assertTrue(is_quorum)

        cm.recv_block_idx_reply(MN_VK2, index_reply2)
        my_quorum -= 1
        is_quorum = not cm._check_idx_reply_quorum() if my_quorum > 0 else cm._check_idx_reply_quorum()
        self.assertTrue(is_quorum)

        cm.recv_block_idx_reply(MN_VK3, index_reply3)
        my_quorum -= 1
        is_quorum = not cm._check_idx_reply_quorum() if my_quorum > 0 else cm._check_idx_reply_quorum()
        self.assertTrue(is_quorum)

        cm.recv_block_idx_reply(MN_VK4, index_reply4)
        my_quorum -= 1
        is_quorum = not cm._check_idx_reply_quorum() if my_quorum > 0 else cm._check_idx_reply_quorum()
        self.assertTrue(is_quorum)

    def test_catchup_with_new_blocks_and_replies_when_we_start_with_some_blocks_already_and_then_we_catchup_again(self, *args):
        """
        Goal :
        - start del with block 1 already
        - 1st round catch up 4 blocks let catchup flag reset
        - 2nd round let catchup start again and complete
        :return:
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        blocks = BlockDataBuilder.create_conseq_blocks(8)

        # # Store the first 2 blocks
        curr_blk = blocks[1]
        self.state.set_latest_block_hash(curr_blk.block_hash)
        self.state.set_latest_block_num(curr_blk.block_num)

        cm = self._build_manager(store_blocks=False)

        cm.run_catchup()

        self.assertFalse(cm.is_catchup_done())

        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]
        MN_VK3 = PhoneBook.masternodes[2]
        MN_VK4 = PhoneBook.masternodes[3]

        all_idx_replies = ()
        reply_datas = []
        for block in blocks[1:]:            # skipping blk 1 since curr_blk wont be included in blk_idx_req
            all_idx_replies = ({'blockNum': block.block_num, 'blockHash': block.block_hash,
                                'blockOwners': [MN_VK1, MN_VK2]},) + all_idx_replies
            reply_datas.append(BlockDataReply.create_from_block(block))


        first_round_idxs = all_idx_replies[4:]
        first_round_blocks = blocks[:4]
        first_round_data = reply_datas[:3]

        second_round_idxs = all_idx_replies[1:4]
        second_round_blocks = blocks[:-1]
        second_round_data = reply_datas[3:]
        second_round_data.pop(3)

        index_reply1 = BlockIndexReply.create(list(first_round_idxs))
        index_reply2 = BlockIndexReply.create(list(first_round_idxs))
        index_reply3 = BlockIndexReply.create(list(first_round_idxs))
        index_reply4 = BlockIndexReply.create(list(first_round_idxs))


        # START OF FIRST ROUND, we catchup to blocknum 4

        cm.recv_block_idx_reply(MN_VK1, index_reply1)  # 5/5
        cm.recv_block_idx_reply(MN_VK3, index_reply2)  # 5/5
        cm.recv_block_idx_reply(MN_VK4, index_reply3)  # 5/5
        cm.recv_block_idx_reply(MN_VK2, index_reply4)  # 5/5

        async def slep(time):
            await asyncio.sleep(time)

        loop.run_until_complete(slep(3))

        self.assertFalse(cm.is_caught_up)

        # Send the BlockDataReplies (round 1)
        for bd_reply in first_round_data:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_caught_up)

        # # Assert we set curr_hash and curr_num to the last added block
        self.assertEqual(cm.curr_hash, first_round_blocks[-1].block_hash)
        self.assertEqual(cm.curr_num, first_round_blocks[-1].block_num)

        # # Assert Redis has been updated
        self.assertEqual(self.state.get_latest_block_num(), first_round_blocks[-1].block_num)
        self.assertEqual(self.state.get_latest_block_hash(), first_round_blocks[-1].block_hash)

        # START OF SECOND ROUND, we catchup to 3 new blocks
        time.sleep(3)
        cm.run_catchup()
        self.assertFalse(cm.is_catchup_done())

        index_reply1 = BlockIndexReply.create(list(second_round_idxs))
        index_reply2 = BlockIndexReply.create(list(second_round_idxs))
        index_reply3 = BlockIndexReply.create(list(second_round_idxs))
        index_reply4 = BlockIndexReply.create(list(second_round_idxs))


        # START OF second ROUND, we catchup to blocknum 4

        cm.recv_block_idx_reply(MN_VK1, index_reply1)  # 5/5
        cm.recv_block_idx_reply(MN_VK3, index_reply2)  # 5/5
        cm.recv_block_idx_reply(MN_VK4, index_reply3)  # 5/5
        cm.recv_block_idx_reply(MN_VK2, index_reply4)  # 5/5

        self.assertFalse(cm.is_caught_up)

        # Send the BlockDataReplies (round 2)
        for bd_reply in second_round_data:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())
        #
        # # Assert we set curr_hash and curr_num to the last added block
        self.assertEqual(cm.curr_hash, second_round_blocks[-1].block_hash)
        self.assertEqual(cm.curr_num, second_round_blocks[-1].block_num)
        #
        # # Assert Redis has been updated
        self.assertEqual(self.state.get_latest_block_num(), second_round_blocks[-1].block_num)
        self.assertEqual(self.state.get_latest_block_hash(), second_round_blocks[-1].block_hash)

    def test_out_of_seq_idx_bd_processing(self, *args):

        blocks = BlockDataBuilder.create_conseq_blocks(4)

        # Store the first 2 blocks
        # curr_blk = blocks[0]
        # StateDriver.set_latest_block_info(block_hash=curr_blk.block_hash, block_num=curr_blk.block_num)

        cm = self._build_manager(store_blocks=False)
        cm.run_catchup()

        MN_VK1 = PhoneBook.masternodes[0]
        MN_VK2 = PhoneBook.masternodes[1]

        all_idx_replies = ()
        reply_datas = []
        for block in reversed(blocks):
            all_idx_replies = all_idx_replies + ({'blockNum': block.block_num, 'blockHash': block.block_hash,
                                                  'blockOwners': [MN_VK1, MN_VK2]},)
            reply_datas.append(BlockDataReply.create_from_block(block))

        first_round_idxs = list(all_idx_replies[2:])
        # first_round_blocks = blocks[:2]
        first_round_data = reply_datas[2:]

        index_reply1 = BlockIndexReply.create(first_round_idxs)
        cm.recv_block_idx_reply(MN_VK1, index_reply1)

        for bd_reply in first_round_data:
            cm.recv_block_data_reply(bd_reply)

        self.assertFalse(cm.is_catchup_done())

        index_reply2 = BlockIndexReply.create(list(all_idx_replies))
        cm.recv_block_idx_reply(MN_VK2, index_reply2)

        for bd_reply in reply_datas:
            cm.recv_block_data_reply(bd_reply)

        self.assertTrue(cm.is_catchup_done())

    def test_catchup_from_new_block_notifs(self, *args):
        cm = self._build_manager(vk=DELE_VK1, store_blocks=False)
        # cm.run_catchup()
        cm.is_caught_up = True
        self.assertTrue(cm.is_catchup_done())

        # TODO should i send this guy an empty block notif so he knows he is caught up at 0??? Bug seems to repro
        # the same anyway

        blocks = BlockDataBuilder.create_conseq_blocks(3)

        new_block_notifs = []
        reply_datas = []
        for block in blocks:
            bd_copy = BlockData.from_bytes(block.serialize())
            reply_datas.append(BlockDataReply.create_from_block(bd_copy))
            new_block_notif = NewBlockNotification.create(block.prev_block_hash, block.block_hash, block.block_num,
                                                          0, block.block_owners, block.input_hashes)
            new_block_notifs.append(new_block_notif)

        # Send the BlockIndexReplies (1 extra)

        assert len(new_block_notifs) == len(reply_datas), "You done goofed this test up davis"

        # Assert that after sending each NBC, we are not caught up, then after receiving the block data we are
        for i in range(len(new_block_notifs)):
            cm.recv_new_blk_notif(new_block_notifs[i])
            self.assertFalse(cm.is_catchup_done())

            cm.recv_block_data_reply(reply_datas[i])
            self.assertTrue(cm.is_catchup_done())


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
