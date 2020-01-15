from unittest import TestCase

from cilantro_ee.nodes.masternode.block_contender import Aggregator, CurrentContenders, SBCInbox, \
    SBCInvalidSignatureError, SBCBlockHashMismatchError, SBCMerkleLeafVerificationError

from cilantro_ee.crypto.wallet import Wallet
from tests import random_txs
from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.sockets.services import _socket
import secrets
from cilantro_ee.core import canonical
import zmq.asyncio
import asyncio


def random_wallets(n=10):
    return [secrets.token_hex(32) for _ in range(n)]

class TestSBCInbox(TestCase):
    def test_verify_sbc_false_sender_ne_merkle_proof_signer(self):
        s = SBCInbox(BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender)

        self.assertFalse(s.sbc_is_valid(sbc.as_reader()))

    def test_verify_sbc_false_invalid_sig(self):
        s = SBCInbox(BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender, idx=0, poisoned_sig=b'\x00' * 64)

        with self.assertRaises(SBCInvalidSignatureError):
            s.sbc_is_valid(sbc.as_reader())

    def test_verify_sbc_false_prev_block_hash_ne_curr_block_hash(self):
        s = SBCInbox(BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'B' * 32, w=sender)

        with self.assertRaises(SBCBlockHashMismatchError):
            s.sbc_is_valid(sbc=sbc.as_reader())

    def test_verify_sbc_false_sbc_merkle_leave_does_not_verify(self):
        s = SBCInbox(BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender, poison_result_hash=True)

        with self.assertRaises(SBCMerkleLeafVerificationError):
            s.sbc_is_valid(sbc=sbc.as_reader())

    def test_verify_sbc_false_tx_hash_not_in_merkle_leaves(self):
        s = SBCInbox(BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender, poison_tx=True)

        with self.assertRaises(SBCMerkleLeafVerificationError):
            s.sbc_is_valid(sbc=sbc.as_reader())

    def test_verify_sbc_true_if_no_failures(self):
        s = SBCInbox(BlockchainDriver(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender)

        s.sbc_is_valid(sbc=sbc.as_reader())


class MockContenders:
    def __init__(self, c):
        self.contenders = c


class MockMerkle:
    def __init__(self, leaves):
        self.leaves = leaves

    def to_dict(self):
        return {
            'leaves': self.leaves
        }

class MockSBC:
    def __init__(self, input, result, index):
        self.inputHash = input
        self.merkleTree = MockMerkle([result])
        self.subBlockNum = index

    def to_dict(self):
        return {
            'inputHash' : self.inputHash,
            'merkleTree': self.merkleTree.to_dict(),
            'subBlockNum': self.subBlockNum
        }


class TestCurrentContenders(TestCase):
    def test_adding_same_input_and_result_adds_to_the_set(self):
        a = MockSBC(1, 2, 1)
        b = MockSBC(1, 2, 3)

        c = [a, b]

        con = CurrentContenders()

        con.add_sbcs(c)

        self.assertEqual(len(con.sbcs[1][2]), 2)

    def test_adding_sbcs_updates_top_vote_initially(self):
        a = MockSBC(1, 2, 1)
        b = MockSBC(2, 2, 3)

        c = [a, b]

        con = CurrentContenders()

        con.add_sbcs(c)

        self.assertEqual(con.top_votes[1], 1)
        self.assertEqual(con.top_votes[2], 1)

    def test_adding_sbcs_doesnt_update_if_not_new_result_different(self):
        a = MockSBC(1, 2, 1)
        b = MockSBC(2, 2, 3)

        c = [a, b]

        con = CurrentContenders()

        con.add_sbcs(c)

        self.assertEqual(con.top_votes[1], 1)
        self.assertEqual(con.top_votes[2], 1)

        a = MockSBC(1, 3, 1)
        b = MockSBC(2, 3, 3)

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.top_votes[1], 1)
        self.assertEqual(con.top_votes[2], 1)

    def test_adding_sbcs_increments_top_vote_if_new_result_multiple_and_more_than_previous_top_vote(self):
        a = MockSBC(1, 2, 1)
        b = MockSBC(2, 2, 3)

        c = [a, b]

        con = CurrentContenders()

        con.add_sbcs(c)

        self.assertEqual(con.top_votes[1], 1)
        self.assertEqual(con.top_votes[2], 1)

        a = MockSBC(1, 3, 1)
        b = MockSBC(2, 3, 3)

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.top_votes[1], 1)
        self.assertEqual(con.top_votes[2], 1)

        a = MockSBC(1, 2, 2)
        b = MockSBC(2, 2, 4)

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.top_votes[1], 2)
        self.assertEqual(con.top_votes[2], 2)

    def test_blocks_added_to_finished_when_quorum_met(self):
        con = CurrentContenders(total_contacts=4)

        a = MockSBC(1, 2, 1)
        b = MockSBC(2, 2, 3)

        c = [a, b]

        con.add_sbcs(c)

        self.assertDictEqual(con.finished, {})

        a = MockSBC(1, 1, 1)
        b = MockSBC(2, 2, 4)

        c = [a, b]

        con.add_sbcs(c)

        self.assertDictEqual(con.finished, {4: b})

    def test_none_added_if_quorum_cannot_be_reached(self):
        con = CurrentContenders(3)

        a = MockSBC(1, 2, 1)

        con.add_sbcs([a])

        self.assertDictEqual(con.finished, {})

        b = MockSBC(1, 3, 1)

        con.add_sbcs([b])

        self.assertDictEqual(con.finished, {})

        aa = MockSBC(1, 4, 1)

        con.add_sbcs([aa])

        self.assertDictEqual(con.finished, {1: None})


class TestAggregator(TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def test_gather_subblocks_all_same_blocks(self):
        a = Aggregator(socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

        c1 = [MockSBC('input_1', 'res_1', 0),
              MockSBC('input_2', 'res_2', 1),
              MockSBC('input_3', 'res_3', 2),
              MockSBC('input_4', 'res_4', 3)]

        c2 = [MockSBC('input_1', 'res_1', 0),
              MockSBC('input_2', 'res_2', 1),
              MockSBC('input_3', 'res_3', 2),
              MockSBC('input_4', 'res_4', 3)]

        c3 = [MockSBC('input_1', 'res_1', 0),
              MockSBC('input_2', 'res_2', 1),
              MockSBC('input_3', 'res_3', 2),
              MockSBC('input_4', 'res_4', 3)]

        c4 = [MockSBC('input_1', 'res_1', 0),
              MockSBC('input_2', 'res_2', 1),
              MockSBC('input_3', 'res_3', 2),
              MockSBC('input_4', 'res_4', 3)]

        a.sbc_inbox.q = [c1, c2, c3, c4]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertEqual(res['subBlocks'][0]['merkleTree']['leaves'][0], 'res_1')
        self.assertEqual(res['subBlocks'][1]['merkleTree']['leaves'][0], 'res_2')
        self.assertEqual(res['subBlocks'][2]['merkleTree']['leaves'][0], 'res_3')
        self.assertEqual(res['subBlocks'][3]['merkleTree']['leaves'][0], 'res_4')

    def test_mixed_results_still_makes_quorum(self):
        a = Aggregator(socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

        c1 = [MockSBC('input_1', 'res_X', 0),
              MockSBC('input_2', 'res_2', 1),
              MockSBC('input_3', 'res_3', 2),
              MockSBC('input_4', 'res_4', 3)]

        c2 = [MockSBC('input_1', 'res_1', 0),
              MockSBC('input_2', 'res_X', 1),
              MockSBC('input_3', 'res_3', 2),
              MockSBC('input_4', 'res_4', 3)]

        c3 = [MockSBC('input_1', 'res_1', 0),
              MockSBC('input_2', 'res_2', 1),
              MockSBC('input_i', 'res_X', 2),
              MockSBC('input_4', 'res_4', 3)]

        c4 = [MockSBC('input_1', 'res_1', 0),
              MockSBC('input_2', 'res_2', 1),
              MockSBC('input_3', 'res_3', 2),
              MockSBC('input_4', 'res_X', 3)]

        a.sbc_inbox.q = [c1, c2, c3, c4]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertEqual(res['subBlocks'][0]['merkleTree']['leaves'][0], 'res_1')
        self.assertEqual(res['subBlocks'][1]['merkleTree']['leaves'][0], 'res_2')
        self.assertEqual(res['subBlocks'][2]['merkleTree']['leaves'][0], 'res_3')
        self.assertEqual(res['subBlocks'][3]['merkleTree']['leaves'][0], 'res_4')

    def test_failed_block_on_one_returns_failed_block(self):
        a = Aggregator(socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

        c1 = [MockSBC('input_1', 'res_X', 0),
                             MockSBC('input_2', 'res_2', 1),
                             MockSBC('input_3', 'res_3', 2),
                             MockSBC('input_4', 'res_4', 3)]

        c2 = [MockSBC('input_1', 'res_1', 0),
                             MockSBC('input_2', 'res_X', 1),
                             MockSBC('input_3', 'res_3', 2),
                             MockSBC('input_4', 'res_4', 3)]

        c3 = [MockSBC('input_1', 'res_X', 0),
                             MockSBC('input_2', 'res_2', 1),
                             MockSBC('input_i', 'res_X', 2),
                             MockSBC('input_4', 'res_4', 3)]

        c4 = [MockSBC('input_1', 'res_1', 0),
                             MockSBC('input_2', 'res_2', 1),
                             MockSBC('input_3', 'res_3', 2),
                             MockSBC('input_4', 'res_X', 3)]

        a.sbc_inbox.q = [c1, c2, c3, c4]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertTrue(canonical.block_is_failed(res, b'\x00' * 32, 1))

    def test_block_dropped_failed_consenus_returns_none(self):
        a = Aggregator(socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

        c1 = [MockSBC('input_1', 'res_1', 0),
                             MockSBC('input_2', 'res_2', 1),
                             MockSBC('input_3', 'res_3', 2),
                             MockSBC('input_4', 'res_4', 3)]

        c2 = [MockSBC('input_1', 'res_1', 0),
                             MockSBC('input_2', 'res_2', 1),
                             MockSBC('input_3', 'res_3', 2),
                             MockSBC('input_4', 'res_4', 3)]

        c3 = [MockSBC('input_1', 'res_1', 0),
                             MockSBC('input_2', 'res_2', 1),
                             MockSBC('input_3', 'res_3', 2),
                             MockSBC('input_4', 'res_X', 3)]

        a.sbc_inbox.q = [c1, c2, c3]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertTrue(canonical.block_is_failed(res, b'\x00' * 32, 1))
