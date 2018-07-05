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
        msg = b'hey this is the block data'

        # is_valid = state._validate_sigs(block=build_test_contender(block_binary=msg))
        #
        # self.assertTrue(is_valid)
        # TODO -- implement

    def test_validate_sigs_bad(self):
        """
        Test _validate_sigs with invalid signatures
        """
        # TODO implement
        pass

    def test_validate_sigs_invalid_delegate(self):
        """
        Test _validate_sigs with a delegate who is not part of the consensus pool
        """
        # TODO implement
        pass

    def test_validate_sigs_invalid_delegate2(self):
        """
        Test _validate_sigs with a signature from an actor who is not even a delegate
        """
        # TODO implement
        pass

    def test_prove_merkle(self):
        """
        Tests _prove_merkle
        """
        # TODO implement
        pass

    def test_prove_merkle_invalid(self):
        """
        Tests _prove_merkle with an invalid merkle proof (hashes don't link up)
        """
        # TODO implement ... failure case for test_validate_merkle
        pass


