
from cilantro_ee.contracts.sync import extract_vk_args, submit_vkbook
from cilantro_ee.crypto import Wallet
from cilantro_ee.core.logger import get_logger
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.messages.message import Message

from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockHandler
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockManager
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockBuilderManager

from tests.utils.constitution_builder import ConstitutionBuilder

from unittest import TestCase
from unittest.mock import MagicMock

import hashlib
import asyncio
import zmq, zmq.asyncio

_log = get_logger("TestSBBuilderManager")

class TestSBManager(TestCase):

    # seed the vkbook
    def seedVKBook(self, num_mn, mn_quorum, num_del, del_quorum):
        self.const_builder = ConstitutionBuilder(num_mn, mn_quorum, num_del,
                                                 del_quorum, False, False)
        book = self.const_builder.get_constitution()
        extract_vk_args(book)
        submit_vkbook(book, overwrite=True)

    def get_hash(self, one_char):
        ih_str = one_char * 64
        return bytes.fromhex(ih_str)

    def get_empty_sbc(self, sb_num, prev_block_hash, wallet):
        
        input_hash = self.get_hash(str(sb_num))

        _log.info("Building empty sub block contender for input hash {}"
                      .format(input_hash.hex()))

        _, merkle_proof = Message.get_message_packed(
                                    MessageType.MERKLE_PROOF,
                                    hash=input_hash,
                                    signer=wallet.verifying_key(),
                                    signature=wallet.sign(input_hash))

        return Message.get_message_packed(MessageType.SUBBLOCK_CONTENDER,
                                   resultHash=input_hash,
                                   inputHash=input_hash,
                                   merkleLeaves=[],
                                   signature=merkle_proof,
                                   transactions=[],
                                   subBlockNum=sb_num,
                                   prevBlockHash=prev_block_hash)

    def get_sbc(self):
        pass

    def get_block_notification(self, block_num, block_owners, sub_blocks):
        # blk_owners = ["abc", "def", "wtf"]
        if len(sub_blocks) == 0:
            return None
        sb_numbers = []
        input_hashes = []
        prev_block_hash = sub_blocks[0].prevBlockHash
        h = hashlib.sha3_256()
        h.update(prev_block_hash)
        is_empty = True
        for sb in sub_blocks:
            if sb.prevBlockHash == prev_block_hash:
                h.update(sb.resultHash)
                sb_numbers.append([sb.subBlockNum])
                input_hashes.append([sb.inputHash])
                if len(sb.transactions) > 0:
                    is_empty = False
        block_hash = h.digest()
        if is_empty:
            _, message = Message.get_message(
                               msg_type=MessageType.BLOCK_NOTIFICATION,
                               blockNum=block_num, blockHash=block_hash,
                               blockOwners=block_owners, subBlockNum=sb_numbers,
                               inputHashes=input_hashes, emptyBlock=None)
        else:
            _, message = Message.get_message(
                               msg_type=MessageType.BLOCK_NOTIFICATION,
                               blockNum=block_num, blockHash=block_hash,
                               blockOwners=block_owners, subBlockNum=sb_numbers,
                               inputHashes=input_hashes, newBlock=None)
        return message


    def setUp(self):
        # basic set up
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.seedVKBook(1, 1, 1, 1)
        self.mock_make_next_sb = MagicMock()
        self.mock_commit_cur_sb = MagicMock()
        self.mock_discord_cur_sb_and_align = MagicMock()

    def get_sb_mgr(self, wallet, mn_quorum=1, num_mn=1, num_sb_builders=1):
        sbb_requests = {
                'make_next_sb': self.mock_make_next_sb,
                'commit_cur_sb': self.mock_commit_cur_sb,
                'discord_cur_sb_and_align': self.mock_discord_cur_sb_and_align}
        bm = SubBlockManager(wallet, self.ctx, _log, sbb_requests,
                             mn_quorum, num_mn, num_sb_builders)
        return bm
                             

    def test_sb_manager_empty_block(self):
        wallet = self.const_builder.get_del_wallets()[0]
        bm = self.get_sb_mgr(wallet)
        prev_block_hash = self.get_hash('0')
        mtype, sb_blob = self.get_empty_sbc(0, prev_block_hash, wallet)
        msg_type, sbc, _, _, is_verified = Message.unpack_message(mtype, sb_blob)
        bm.sb_handler.add_sub_block(sbc)
        block_notif = self.get_block_notification(1, [], [sbc])
        # mock block_fetcher's interface functions

        tasks = asyncio.gather(
            bm.handle_block_notification(block_notif, b'xyxljfld'),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.mock_commit_cur_sb.assert_called()
        self.mock_make_next_sb.assert_called()
        # self.assertListEqual(s.received, [(b'howdy', 'inproc://test1'), (b'howdy2', 'inproc://test1')])
        # bm.start_catchup_process()
        # verify bm's db should be update
        # do various block notifications
        # newblock, skipblock, failblock and verify appropriate actions and state
        # add_sub_block too to verify that newblock matching and non-matching states


    def test_sb_manager_fail_block(self):
        wallet = self.const_builder.get_del_wallets()[0]
        bm = self.get_sb_mgr(wallet)
        prev_block_hash = self.get_hash('1')
        mtype, sb_blob = self.get_empty_sbc(0, prev_block_hash, wallet)
        msg_type, sbc, _, _, is_verified = Message.unpack_message(mtype, sb_blob)
        bm.sb_handler.add_sub_block(sbc)
        block_notif = self.get_block_notification(1, [], [sbc])

        tasks = asyncio.gather(
            bm.handle_block_notification(block_notif, b'xyxljfld'),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.mock_discord_cur_sb_and_align.assert_called()
        self.mock_make_next_sb.assert_called()


class TestSBBuilderManager(TestCase):

    def test_sb_handler(self):
        sbh = SubBlockHandler(3)

    def test_sbb_manager(self):
        wallet = Wallet()
        sbbm = SubBlockBuilderManager(ip='127.0.0.1', signing_key=wallet.signing_key().hex())

