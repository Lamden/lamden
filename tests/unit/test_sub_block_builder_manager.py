
from cilantro_ee.contracts.sync import extract_vk_args, submit_vkbook
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.logger.base import get_logger
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message

from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockHandler
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockManager
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockBuilderManager

from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.utils import int_to_bytes

from tests.utils.constitution_builder import ConstitutionBuilder

from unittest import TestCase
from unittest import mock
from unittest.mock import MagicMock

import asyncio
import zmq, zmq.asyncio

_log = get_logger("TestSBBuilderManager")

ctx = zmq.asyncio.Context()
const_builder = ConstitutionBuilder(1, 1, 1, 1, False, False)
book = const_builder.get_constitution()
extract_vk_args(book)
submit_vkbook(book, overwrite=True)


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
        wallet = Wallet()
        sbb_requests = {
                'make_next_sb': self.mock_make_next_sb,
                'commit_cur_sb': self.mock_commit_cur_sb,
                'discord_cur_sb_and_align': self.mock_discord_cur_sb_and_align}
        bm = SubBlockManager(wallet.signing_key(), wallet.verifying_key(),
                             sbb_requests, 2, 3, 3)
                             

    def test_sbb_manager(self):
        wallet = Wallet()
        sbbm = SubBlockBuilderManager(ip='127.0.0.1', signing_key=wallet.signing_key().hex())

