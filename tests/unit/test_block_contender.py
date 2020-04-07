from unittest import TestCase

from cilantro_ee.nodes.masternode.block_contender import CurrentContenders
from cilantro_ee.nodes.masternode.new_contender import BlockContender, SubBlockContender, PotentialSolution

import secrets

class MockContenders:
    def __init__(self, c):
        self.contenders = c


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

        self.assertTrue(con.subblock_has_consensus(3))

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


