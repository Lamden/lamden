
from cilantro_ee.contracts.sync import extract_vk_args, submit_vkbook
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.logger.base import get_logger
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message

from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockHandler
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockManager
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockBuilderManager

from cilantro_ee.services.storage.vkbook import VKBook
from tests.utils.constitution_builder import ConstitutionBuilder

from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock

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

    def setUp(self):
        # basic set up
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.seedVKBook(1, 1, 1, 1)
        self.mock_make_next_sb = MagicMock()
        self.mock_commit_cur_sb = MagicMock()
        self.mock_discord_cur_sb_and_align = MagicMock()

    def get_sb_mgr(self, wallet, mn_quorum=2, num_mn=3, num_sb_builders=3):
        sbb_requests = {
                'make_next_sb': self.mock_make_next_sb,
                'commit_cur_sb': self.mock_commit_cur_sb,
                'discord_cur_sb_and_align': self.mock_discord_cur_sb_and_align}
        bm = SubBlockManager(wallet.signing_key(), wallet.verifying_key(),
                             sbb_requests, mn_quorum, num_mn, num_sb_builders)
        return bm
                             


    # catchup mgr set up and follow up action when done
    # getting all the sbs before blk notification and after - variations of this is the meat of testing
    #     newblk notifi, empty block, failed block, etc
    #     need utility to make sub-blocks - empty, full, etc
    def test_sb_manager_start(self):
        wallet = self.const_builder.get_del_wallets()[0]
        bm = self.get_sb_mgr(wallet)
        bm.setup_catchup_mgr(wallet, self.ctx)
        # mock block_fetcher's interface functions
        # bm.start_catchup_process()
        # verify bm's db should be update
        # do various block notifications
        # newblock, skipblock, failblock and verify appropriate actions and state
        # add_sub_block too to verify that newblock matching and non-matching states


class TestSBBuilderManager(TestCase):

    def test_sb_handler(self):
        sbh = SubBlockHandler(3)

    def test_sbb_manager(self):
        wallet = Wallet()
        sbbm = SubBlockBuilderManager(ip='127.0.0.1', signing_key=wallet.signing_key().hex())

