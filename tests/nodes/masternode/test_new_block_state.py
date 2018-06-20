from unittest import TestCase
from unittest.mock import MagicMock, patch
from cilantro.nodes.masternode.masternode import MNBootState, MNRunState
from cilantro.nodes.masternode.new_block import MNNewBlockState
from cilantro.protocol.statemachine import *
from cilantro.messages.consensus.block_contender import BlockContender, build_test_contender, build_test_merkle_sig


class TestMasterNodeNewBlockState(TestCase):

    def test_reset_attrs(self):
        mock_sm = MagicMock()
        state = MNNewBlockState(mock_sm)

        state.reset_attrs()

        self.assertTrue(len(state.pending_blocks) == 0)
        self.assertTrue(state.current_block is None)

    def test_validate_sigs(self):
        """
        Tests the _validate_sigs
        """
        mock_sm = MagicMock()
        state = MNNewBlockState(mock_sm)

        msg = b'oh hi there'
        sigs = [build_test_merkle_sig(msg=msg) for _ in range(8)]

        is_valid = state.validate_block_contender._validate_sigs(sigs)

    def test_validate_merkle(self):
        pass