from unittest import TestCase

from cilantro_ee.nodes.masternode.contender import BlockContender, SubBlockContender, PotentialSolution, Aggregator
import zmq.asyncio
import asyncio
from cilantro_ee.sockets.struct import _socket
from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.crypto import canonical
import secrets
from cilantro_ee.crypto.wallet import Wallet


class MockContenders:
    def __init__(self, c):
        self.contenders = c


class MockTx:
    def __init__(self):
        self.tx = secrets.token_hex(6)

    def to_dict(self):
        return self.tx


class MockMerkle:
    def __init__(self, leaves):
        self.leaves = leaves
        self.signature = secrets.token_hex(8)

    def to_dict(self):
        return {
            'leaves': self.leaves
        }

class MockSBC:
    def __init__(self, input, result, index):
        self.inputHash = input
        self.merkleTree = MockMerkle([result])
        self.subBlockNum = index
        self.signer = secrets.token_hex(8)
        self.transactions = [MockTx() for _ in range(12)]
        self.prevBlockHash = 0

    def to_dict(self):
        return {
            'inputHash': self.inputHash,
            'merkleTree': self.merkleTree.to_dict(),
            'subBlockNum': self.subBlockNum
        }


class TestCurrentContenders(TestCase):
    def test_adding_same_input_and_result_adds_to_the_set(self):
        # Input: 2 blocks

        a = MockSBC(1, 2, 3)
        b = MockSBC(1, 2, 3)

        c = [a, b]

        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        sb = con.subblock_contenders[3]

        self.assertEqual(sb.potential_solutions[2].votes, 2)

    def test_adding_sbcs_updates_top_vote_initially(self):
        # Input: 2 blocks with different input hashes

        a = MockSBC(1, 2, 1)
        b = MockSBC(2, 2, 3)

        c = [a, b]

        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)

    def test_adding_sbcs_doesnt_update_if_not_new_result_different(self):
        # Input: 2 blocks with different result hashes, but same input and index

        # Check: votes for each potential solution is 1

        # Input: 2 blocks with more different results
        # Check; votes for the first two potential solutions is still one
        a = MockSBC(input=1, result=2, index=1)
        b = MockSBC(input=2, result=2, index=3)

        c = [a, b]

        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

        a = MockSBC(input=1, result=3, index=1)
        b = MockSBC(input=2, result=3, index=3)

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

    def test_adding_sbcs_increments_top_vote_if_new_result_multiple_and_more_than_previous_top_vote(self):
        a = MockSBC(input=1, result=2, index=1)
        b = MockSBC(input=2, result=2, index=3)

        c = [a, b]

        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

        a = MockSBC(input=1, result=3, index=1)
        b = MockSBC(input=2, result=3, index=3)

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

        a = MockSBC(input=1, result=2, index=1)
        b = MockSBC(input=2, result=2, index=3)

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 2)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 2)

    def test_blocks_added_to_finished_when_quorum_met(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1)
        b = MockSBC(input=2, result=2, index=3)

        c = [a, b]

        con.add_sbcs(c)

        self.assertFalse(con.block_has_consensus())

        a = MockSBC(1, 1, 1)
        b = MockSBC(2, 2, 3)

        c = [a, b]

        con.add_sbcs(c)

        self.assertTrue(con.subblock_contenders[3].has_required_consensus)

    def test_out_of_range_index_not_added(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1)
        b = MockSBC(input=2, result=2, index=300)

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.current_responded_sbcs(), 1)

    def test_subblock_has_consensus_false_if_not_quorum(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1)

        c = [a]

        con.add_sbcs(c)

        self.assertFalse(con.subblock_contenders[1].has_required_consensus)

    def test_block_true_if_all_blocks_have_consensus(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1)
        b = MockSBC(input=1, result=2, index=1)

        c = MockSBC(input=1, result=2, index=2)
        d = MockSBC(input=1, result=2, index=2)

        e = MockSBC(input=1, result=2, index=3)
        f = MockSBC(input=1, result=2, index=3)

        g = MockSBC(input=1, result=2, index=0)
        h = MockSBC(input=1, result=2, index=0)

        con.add_sbcs([a, b, c, d, e, f, g, h])

        self.assertTrue(con.block_has_consensus())

    def test_block_false_if_one_subblocks_doesnt_have_consensus(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1)
        b = MockSBC(input=1, result=2, index=1)

        c = MockSBC(input=1, result=2, index=2)
        d = MockSBC(input=1, result=2, index=2)

        e = MockSBC(input=1, result=2, index=3)
        # f = MockSBC(input=1, result=2, index=3)

        g = MockSBC(input=1, result=2, index=0)
        h = MockSBC(input=1, result=2, index=0)

        con.add_sbcs([a, b, c, d, e, g, h])

        self.assertFalse(con.block_has_consensus())

    def test_block_false_if_one_subblock_is_none(self):
        con = BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        a = MockSBC(input=1, result=2, index=1)
        b = MockSBC(input=1, result=2, index=1)

        c = MockSBC(input=1, result=2, index=2)
        d = MockSBC(input=1, result=2, index=2)

        # e = MockSBC(input=1, result=2, index=3)
        # f = MockSBC(input=1, result=2, index=3)

        g = MockSBC(input=1, result=2, index=0)
        h = MockSBC(input=1, result=2, index=0)

        con.add_sbcs([a, b, c, d, g, h])

        self.assertFalse(con.block_has_consensus())
    # def test_none_added_if_quorum_cannot_be_reached(self):
    #     con = CurrentContenders(3)
    #
    #     a = MockSBC(1, 2, 1)
    #
    #     con.add_sbcs([a])
    #
    #     self.assertDictEqual(con.finished, {})
    #
    #     b = MockSBC(1, 3, 1)
    #
    #     con.add_sbcs([b])
    #
    #     self.assertDictEqual(con.finished, {})
    #
    #     aa = MockSBC(1, 4, 1)
    #
    #     con.add_sbcs([aa])
    #
    #     self.assertDictEqual(con.finished, {1: None})



class TestAggregator(TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def test_gather_subblocks_all_same_blocks(self):
        a = Aggregator(wallet=Wallet(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

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

        self.assertEqual(res['subBlocks'][0]['merkleLeaves'][0], 'res_1')
        self.assertEqual(res['subBlocks'][1]['merkleLeaves'][0], 'res_2')
        self.assertEqual(res['subBlocks'][2]['merkleLeaves'][0], 'res_3')
        self.assertEqual(res['subBlocks'][3]['merkleLeaves'][0], 'res_4')

    def test_mixed_results_still_makes_quorum(self):
        a = Aggregator(wallet=Wallet(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

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

        self.assertEqual(res['subBlocks'][0]['merkleLeaves'][0], 'res_1')
        self.assertEqual(res['subBlocks'][1]['merkleLeaves'][0], 'res_2')
        self.assertEqual(res['subBlocks'][2]['merkleLeaves'][0], 'res_3')
        self.assertEqual(res['subBlocks'][3]['merkleLeaves'][0], 'res_4')

    def test_failed_block_on_one_returns_failed_block(self):
        a = Aggregator(wallet=Wallet(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

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

        print(res)

        self.assertTrue(canonical.block_is_failed(res, '0' * 64, 1))

    def test_block_never_received_goes_through_adequate_consensus(self):
        a = Aggregator(wallet=Wallet(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context(), driver=BlockchainDriver())

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

        res = self.loop.run_until_complete(a.gather_subblocks(4, adequate_ratio=0.3))

        print(res)

        self.assertFalse(canonical.block_is_failed(res, '0' * 32, 1))
