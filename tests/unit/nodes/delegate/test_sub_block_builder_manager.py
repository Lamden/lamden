import asyncio
from cilantro_ee.utils.test.testnet_config import set_testnet_config
set_testnet_config('vk_dump.json')

from cilantro_ee.core.logger.base import get_logger

from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockHandler
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockManager
from cilantro_ee.utils import int_to_bytes

from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock

from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.crypto.wallet import Wallet

_log = get_logger("TestSBBuilderManager")

from cilantro_ee.constants.testnet import TESTNET_DELEGATES, TESTNET_MASTERNODES
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.constants.testnet import TESTNET_DELEGATES
TEST_IP = '127.0.0.1'
TEST_SK = TESTNET_DELEGATES[0]['sk']


class TestSBBuilderManager(TestCase):

    def mock_make_next_sb(self):
        pass

    def mock_commit_cur_sb(self):
        pass

    def mock_discord_cur_sb_and_align(self, sb_numbers, input_hashes):
        pass

    def test_sb_handler(self):
        sbh = SubBlockHandler(3)

    def test_sb_manager(self):
        wallet = Wallet(TEST_SK)
        sbb_requests = {
                'make_next_sb': self.mock_make_next_sb,
                'commit_cur_sb': self.mock_commit_cur_sb,
                'discord_cur_sb_and_align': self.mock_discord_cur_sb_and_align}
        bm = SubBlockManager(wallet.signing_key(), wallet.verifying_key(),
                             sbb_requests, 3, 4)
                             

