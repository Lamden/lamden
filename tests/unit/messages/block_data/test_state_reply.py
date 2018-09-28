from cilantro.messages.block_data.state_update import StateUpdateReply
from cilantro.messages.block_data.block_data import BlockDataBuilder
from cilantro.constants.masternode import SUBBLOCKS_REQUIRED
from unittest import TestCase
import secrets
from unittest import mock


class StateReplyTest(TestCase):

    def test_init(self):
        fbmds = [BlockDataBuilder.create_block(sub_block_count=1) for _ in range(4)]

        sr = StateUpdateReply.create(fbmds)

        self.assertEqual(fbmds, sr.block_data)

    def test_serialization(self):
        """
        Tests serialize and from_bytes are inverse operations
        """
        fbmds = [BlockDataBuilder.create_block(sub_block_count=1) for _ in range(4)]

        sr = StateUpdateReply.create(fbmds)
        sr_bin = sr.serialize()

        sr_clone = StateUpdateReply.from_bytes(sr_bin)

        self.assertEqual(sr, sr_clone)
