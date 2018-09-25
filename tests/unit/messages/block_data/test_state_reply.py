from cilantro.messages.block_data.state_update import StateUpdateReply
from cilantro.messages.block_data.block_metadata import FullBlockData
from cilantro.constants.masternode import SUBBLOCKS_REQUIRED
from unittest import TestCase
import secrets


# TODO delete this once we remove it from MN
class StateRequestTest(TestCase):

    def _build_test_block_data(self):
        b_hash = 'AB' * 32
        merkle_roots = ['A' * 64 for _ in range(SUBBLOCKS_REQUIRED)]
        prev_b_hash = 'E' * 64
        mn_sig = 'C' * 128
        timestamp = 9000
        txs = [secrets.token_bytes(16) for _ in range(2)]

        bd = FullBlockData.create(block_hash=b_hash, merkle_roots=merkle_roots, prev_block_hash=prev_b_hash,
                                  timestamp=timestamp, masternode_signature=mn_sig, raw_transactions=txs)
        return bd

    def test_init(self):
        block_data = [self._build_test_block_data() for _ in range(4)]

        sr = StateUpdateReply.create(block_data)

        self.assertEqual(block_data, sr.block_data)

    def test_serialization(self):
        """
        Tests serialize and from_bytes are inverse operations
        """
        block_data = [self._build_test_block_data() for _ in range(4)]

        sr = StateUpdateReply.create(block_data)
        sr_bin = sr.serialize()

        sr_clone = StateUpdateReply.from_bytes(sr_bin)

        self.assertEqual(sr, sr_clone)
