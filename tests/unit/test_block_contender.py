from unittest import TestCase
from contracting.db.encoder import encode, decode
from lamden.crypto.canonical import merklize, block_from_subblocks

from lamden.crypto.wallet import Wallet
from lamden.nodes.masternode import contender
import asyncio
import secrets

from contracting.db.driver import ContractDriver


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
            'leaves': self.leaves,
            'signature': self.signature
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
            'input_hash': self.inputHash,
            'merkle_tree': self.merkleTree.to_dict(),
            'subblock': self.subBlockNum,
            'signer': self.signer,
            'transactions': [],
            'previous': secrets.token_hex(8)
        }


subblock = {
    'input_hash': 'a',
    'transactions': [],
    'merkle_tree': {
        'leaves': [
            'a', 'b', 'c'
        ],
        'signature': 'x'
    },
    'subblock': 0,
    'previous': 'b',
    'signer': 'a'
}

subblock2 = {
    'input_hash': 'a',
    'transactions': [],
    'merkle_tree': {
        'leaves': [
            'a', 'b', 'c'
        ],
        'signature': 'a'
    },
    'subblock': 0,
    'previous': 'b',
    'signer': 'x'
}


class TestPotentialSolution(TestCase):
    def test_struct_to_dict_appends_signature_tuple_and_sorts(self):
        p = contender.PotentialSolution(struct=subblock)

        p.signatures.append(('b', 'x'))
        p.signatures.append(('x', 'b'))

        expected = {
            'input_hash': 'a',
            'transactions': [],
            'merkle_leaves': ['a', 'b', 'c'],
            'subblock': 0,
            'signatures': [
                {
                    'signature': 'x',
                    'signer': 'b'
                },
                {
                    'signature': 'b',
                    'signer': 'x'
                },
            ]
        }

        self.assertDictEqual(p.struct_to_dict(), expected)

    def test_votes_returns_len_of_sigs(self):
        p = contender.PotentialSolution(struct=subblock)

        p.signatures.append(('b', 'x'))
        p.signatures.append(('x', 'b'))

        self.assertEqual(p.votes, 2)


class TestCurrentContenders(TestCase):
    def test_adding_same_input_and_result_adds_to_the_set(self):
        # Input: 2 blocks

        res = secrets.token_hex(8)

        a = MockSBC(1, res, 3).to_dict()
        b = MockSBC(1, res, 3).to_dict()

        c = [a, b]

        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        sb = con.subblock_contenders[3]

        self.assertEqual(sb.potential_solutions[res].votes, 2)

    def test_adding_sbcs_updates_top_vote_initially(self):
        # Input: 2 blocks with different input hashes
        res_1 = secrets.token_hex(8)
        a = MockSBC(1, res_1, 1).to_dict()
        b = MockSBC(2, res_1, 3).to_dict()

        c = [a, b]

        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)

    def test_adding_sbcs_doesnt_update_if_not_new_result_different(self):
        # Input: 2 blocks with different result hashes, but same input and index

        # Check: votes for each potential solution is 1

        # Input: 2 blocks with more different results
        # Check; votes for the first two potential solutions is still one
        res_1 = secrets.token_hex(8)
        a = MockSBC(input=1, result=res_1, index=1).to_dict()
        b = MockSBC(input=2, result=res_1, index=3).to_dict()

        c = [a, b]

        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

        res_2 = secrets.token_hex(8)
        a = MockSBC(input=1, result=res_2, index=1).to_dict()
        b = MockSBC(input=2, result=res_2, index=3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

    def test_adding_sbcs_increments_top_vote_if_new_result_multiple_and_more_than_previous_top_vote(self):
        res_1 = secrets.token_hex(8)
        a = MockSBC(input=1, result=res_1, index=1).to_dict()
        b = MockSBC(input=2, result=res_1, index=3).to_dict()

        c = [a, b]

        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

        res_2 = secrets.token_hex(8)
        a = MockSBC(input=1, result=res_2, index=1).to_dict()
        b = MockSBC(input=2, result=res_2, index=3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 1)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 1)

        a = MockSBC(input=1, result=res_1, index=1).to_dict()
        b = MockSBC(input=2, result=res_1, index=3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.subblock_contenders[1].best_solution.votes, 2)
        self.assertEqual(con.subblock_contenders[3].best_solution.votes, 2)

    def test_has_required_consensus_false_if_best_solution_none(self):
        con = contender.SubBlockContender(input_hash='a' * 64, index=0, total_contacts=2, required_consensus=0.66)
        self.assertFalse(con.has_required_consensus)

    def test_has_adequate_consensus_false_if_best_solution_none(self):
        con = contender.SubBlockContender(input_hash='a' * 64, index=0, total_contacts=2, required_consensus=0.66)
        self.assertFalse(con.has_adequate_consensus)

    def test_not_failed_if_no_responses_yet(self):
        con = contender.SubBlockContender(input_hash='a' * 64, index=0, total_contacts=2, required_consensus=0.66)
        self.assertFalse(con.failed)

    def test_failed_if_enough_responses_but_no_consensus(self):
        con = contender.SubBlockContender(input_hash='a' * 64, index=0, total_contacts=2, required_consensus=0.66)
        con.total_responses = 10
        self.assertTrue(con.failed)

    def test_has_adequate_consensus_false_if_no_votes_on_any_solution(self):
        con = contender.SubBlockContender(input_hash='a' * 64, index=0, total_contacts=2, required_consensus=0.66)
        con.total_contacts = 100

        con.best_solution = contender.PotentialSolution(struct={})
        con.best_solution.signatures = ['a', 'b', 'c']

        self.assertFalse(con.has_adequate_consensus)

    def test_has_adequate_consensus_true_if_enough_votes(self):
        con = contender.SubBlockContender(input_hash='a' * 64, index=0, total_contacts=2, required_consensus=0.66)
        con.total_contacts = 3

        con.best_solution = contender.PotentialSolution(struct={})
        con.best_solution.signatures = ['a', 'b', 'c']

        self.assertTrue(con.has_adequate_consensus)

    def test_serialized_solution_none_if_not_adequate_consensus(self):
        con = contender.SubBlockContender(input_hash='a' * 64, index=0, total_contacts=2, required_consensus=0.66)
        con.total_contacts = 100

        con.best_solution = contender.PotentialSolution(struct={})
        con.best_solution.signatures = ['a', 'b', 'c']

        self.assertIsNone(con.serialized_solution)

    def test_serialized_solution_none_if_failed(self):
        con = contender.SubBlockContender(input_hash='a' * 64, index=0, total_contacts=2, required_consensus=0.66)
        con.total_responses = 10

        self.assertIsNone(con.serialized_solution)

    def test_serialized_solution_returns_best_solution_as_dict(self):
        con = contender.SubBlockContender(input_hash='a' * 64, index=0, total_contacts=2, required_consensus=0.66)
        con.add_potential_solution(subblock)

        #p.signatures.append(('b', 'x'))
        #p.signatures.append(('x', 'b'))

        expected = {
            'input_hash': 'a',
            'transactions': [],
            'merkle_leaves': ['a', 'b', 'c'],
            'subblock': 0,
            'previous': 'b',
            'signatures': [
                {
                    'signature': 'x',
                    'signer': 'b'
                },
                {
                    'signature': 'b',
                    'signer': 'x'
                },
            ]
        }

    def test_blocks_added_to_finished_when_quorum_met(self):
        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        res_1 = secrets.token_hex(8)

        a = MockSBC(input=1, result=res_1, index=1).to_dict()
        b = MockSBC(input=2, result=res_1, index=3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertFalse(con.block_has_consensus())

        res_2 = secrets.token_hex(8)

        a = MockSBC(1, res_2, 1).to_dict()
        b = MockSBC(2, res_1, 3).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertTrue(con.subblock_contenders[3].has_required_consensus)

    def test_out_of_range_index_not_added(self):
        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        res_1 = secrets.token_hex(8)

        a = MockSBC(input=1, result=res_1, index=1).to_dict()
        b = MockSBC(input=2, result=res_1, index=300).to_dict()

        c = [a, b]

        con.add_sbcs(c)

        self.assertEqual(con.current_responded_sbcs(), 1)

    def test_subblock_has_consensus_false_if_not_quorum(self):
        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        res_1 = secrets.token_hex(8)

        a = MockSBC(input=1, result=res_1, index=1).to_dict()

        c = [a]

        con.add_sbcs(c)

        self.assertFalse(con.subblock_contenders[1].has_required_consensus)

    def test_block_true_if_all_blocks_have_consensus(self):
        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        res_1 = secrets.token_hex(8)

        a = MockSBC(input=1, result=res_1, index=1).to_dict()
        b = MockSBC(input=1, result=res_1, index=1).to_dict()

        c = MockSBC(input=1, result=res_1, index=2).to_dict()
        d = MockSBC(input=1, result=res_1, index=2).to_dict()

        e = MockSBC(input=1, result=res_1, index=3).to_dict()
        f = MockSBC(input=1, result=res_1, index=3).to_dict()

        g = MockSBC(input=1, result=res_1, index=0).to_dict()
        h = MockSBC(input=1, result=res_1, index=0).to_dict()

        con.add_sbcs([a, b, c, d, e, f, g, h])

        self.assertTrue(con.block_has_consensus())

    def test_block_false_if_one_subblocks_doesnt_have_consensus(self):
        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        res_1 = secrets.token_hex(8)

        a = MockSBC(input=1, result=res_1, index=1).to_dict()
        b = MockSBC(input=1, result=res_1, index=1).to_dict()

        c = MockSBC(input=1, result=res_1, index=2).to_dict()
        d = MockSBC(input=1, result=res_1, index=2).to_dict()

        e = MockSBC(input=1, result=res_1, index=3).to_dict()
        # f = MockSBC(input=1, result=2, index=3)

        g = MockSBC(input=1, result=res_1, index=0).to_dict()
        h = MockSBC(input=1, result=res_1, index=0).to_dict()

        con.add_sbcs([a, b, c, d, e, g, h])

        self.assertFalse(con.block_has_consensus())

    def test_block_false_if_one_subblock_is_none(self):
        con = contender.BlockContender(total_contacts=2, required_consensus=0.66, total_subblocks=4)

        res_1 = secrets.token_hex(9)

        a = MockSBC(input=1, result=res_1, index=1).to_dict()
        b = MockSBC(input=1, result=res_1, index=1).to_dict()

        c = MockSBC(input=1, result=res_1, index=2).to_dict()
        d = MockSBC(input=1, result=res_1, index=2).to_dict()

        # e = MockSBC(input=1, result=2, index=3)
        # f = MockSBC(input=1, result=2, index=3)

        g = MockSBC(input=1, result=res_1, index=0).to_dict()
        h = MockSBC(input=1, result=res_1, index=0).to_dict()

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
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_gather_subblocks_all_same_blocks(self):
        a = contender.Aggregator(driver=ContractDriver())

        c1 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c2 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c3 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c4 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        a.sbc_inbox.q = [c1, c2, c3, c4]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertEqual(res['subblocks'][0]['merkle_leaves'][0], 'res_1')
        self.assertEqual(res['subblocks'][1]['merkle_leaves'][0], 'res_2')
        self.assertEqual(res['subblocks'][2]['merkle_leaves'][0], 'res_3')
        self.assertEqual(res['subblocks'][3]['merkle_leaves'][0], 'res_4')

    def test_mixed_results_still_makes_quorum(self):
        a = contender.Aggregator(driver=ContractDriver())

        c1 = [MockSBC('input_1', 'res_X', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c2 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_X', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c3 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_i', 'res_X', 2).to_dict(),
              MockSBC('input_4', 'res_4', 3).to_dict()]

        c4 = [MockSBC('input_1', 'res_1', 0).to_dict(),
              MockSBC('input_2', 'res_2', 1).to_dict(),
              MockSBC('input_3', 'res_3', 2).to_dict(),
              MockSBC('input_4', 'res_X', 3).to_dict()]

        a.sbc_inbox.q = [c1, c2, c3, c4]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertEqual(res['subblocks'][0]['merkle_leaves'][0], 'res_1')
        self.assertEqual(res['subblocks'][1]['merkle_leaves'][0], 'res_2')
        self.assertEqual(res['subblocks'][2]['merkle_leaves'][0], 'res_3')
        self.assertEqual(res['subblocks'][3]['merkle_leaves'][0], 'res_4')

    def test_failed_block_on_one_removes_subblock_from_block(self):
        a = contender.Aggregator(driver=ContractDriver())

        c1 = [MockSBC('input_1', 'res_X', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c2 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_X', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c3 = [MockSBC('input_1', 'res_X', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_i', 'res_X', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c4 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_X', 3).to_dict()]

        a.sbc_inbox.q = [c1, c2, c3, c4]

        res = self.loop.run_until_complete(a.gather_subblocks(4))

        self.assertTrue(len(res['subblocks']) == 3)

    def test_block_never_received_goes_through_adequate_consensus(self):
        a = contender.Aggregator(
            driver=ContractDriver(),
            seconds_to_timeout=0.5
        )

        c1 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c2 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_4', 3).to_dict()]

        c3 = [MockSBC('input_1', 'res_1', 0).to_dict(),
                             MockSBC('input_2', 'res_2', 1).to_dict(),
                             MockSBC('input_3', 'res_3', 2).to_dict(),
                             MockSBC('input_4', 'res_X', 3).to_dict()]

        a.sbc_inbox.q = [c1, c2, c3]

        res = self.loop.run_until_complete(a.gather_subblocks(4, adequate_ratio=0.3))

        self.assertNotEqual(res['hash'], 'f' * 64)


class TestSBCProcessor(TestCase):
    def test_subblock_with_bad_sb_idx_returns_false(self):
        sbc = {
            'subblock': 1
        }

        s = contender.SBCInbox()

        self.assertFalse(s.sbc_is_valid(sbc, 2))

    def test_verify_signature_not_valid_no_transactions(self):
        w = Wallet()
        w2 = Wallet()

        input_hash = 'something'
        signature = w2.sign(input_hash)

        sbc = {
            'subblock': 1,
            'transactions': [],
            'input_hash': input_hash,
            'signer': w.verifying_key,
            'merkle_tree': {
                'signature': signature
            }
        }

        s = contender.SBCInbox()

        self.assertFalse(s.sbc_is_valid(sbc, 1))

    def test_verify_signature_not_valid_transactions(self):
        tx_1 = {
            'something': 'who_cares'
        }

        tx_2 = {
            'something_else': 'who_cares'
        }

        txs = [encode(tx).encode() for tx in [tx_1, tx_2]]
        expected_tree = merklize(txs)

        w = Wallet()
        w2 = Wallet()

        input_hash = 'something'
        signature = w2.sign(expected_tree[0])

        sbc = {
            'subblock': 1,
            'transactions': [tx_1, tx_2],
            'input_hash': input_hash,
            'signer': w.verifying_key,
            'merkle_tree': {
                'signature': signature,
                'leaves': expected_tree
            }
        }

        s = contender.SBCInbox()

        self.assertFalse(s.sbc_is_valid(sbc, 1))

    def test_bad_merkle_tree_missing_fails(self):
        tx_1 = {
            'something': 'who_cares'
        }

        tx_2 = {
            'something_else': 'who_cares'
        }

        txs = [encode(tx).encode() for tx in [tx_1, tx_2]]
        expected_tree = merklize(txs)

        w = Wallet()

        input_hash = 'something'
        signature = w.sign(expected_tree[0])

        sbc = {
            'subblock': 1,
            'transactions': [tx_1, tx_2],
            'input_hash': input_hash,
            'signer': w.verifying_key,
            'merkle_tree': {
                'signature': signature,
                'leaves': expected_tree[0:1]
            }
        }

        s = contender.SBCInbox()

        self.assertFalse(s.sbc_is_valid(sbc, 1))

    def test_bad_merkle_leaf_in_tree(self):
        tx_1 = {
            'something': 'who_cares'
        }

        tx_2 = {
            'something_else': 'who_cares'
        }

        txs = [encode(tx).encode() for tx in [tx_1, tx_2]]
        expected_tree = merklize(txs)

        w = Wallet()

        input_hash = 'something'
        signature = w.sign(expected_tree[0])

        expected_tree[1] = 'crap'

        sbc = {
            'subblock': 1,
            'transactions': [tx_1, tx_2],
            'input_hash': input_hash,
            'signer': w.verifying_key,
            'merkle_tree': {
                'signature': signature,
                'leaves': expected_tree
            }
        }

        s = contender.SBCInbox()

        self.assertFalse(s.sbc_is_valid(sbc, 1))

    def test_good_sbc_returns_true(self):
        tx_1 = {
            'something': 'who_cares'
        }

        tx_2 = {
            'something_else': 'who_cares'
        }

        txs = [encode(tx).encode() for tx in [tx_1, tx_2]]
        expected_tree = merklize(txs)

        w = Wallet()

        input_hash = 'something'
        signature = w.sign(expected_tree[0])

        sbc = {
            'subblock': 1,
            'transactions': [tx_1, tx_2],
            'input_hash': input_hash,
            'signer': w.verifying_key,
            'merkle_tree': {
                'signature': signature,
                'leaves': expected_tree
            }
        }

        s = contender.SBCInbox()

        self.assertTrue(s.sbc_is_valid(sbc, 1))

    def test_process_message_good_and_bad_sbc_doesnt_pass_to_q(self):
        ### GOOD SBC
        tx_1_1 = {
            'something': 'who_cares'
        }

        tx_1_2 = {
            'something_else': 'who_cares'
        }

        txs = [encode(tx).encode() for tx in [tx_1_1, tx_1_2]]
        expected_tree = merklize(txs)

        w = Wallet()

        input_hash = 'something'
        signature = w.sign(expected_tree[0])

        sbc_1 = {
            'subblock': 0,
            'transactions': [tx_1_1, tx_1_2],
            'input_hash': input_hash,
            'signer': w.verifying_key,
            'merkle_tree': {
                'signature': signature,
                'leaves': expected_tree
            }
        }

        ### BAD SBC
        tx_2_1 = {
            'something': 'who_cares2'
        }

        tx_2_2 = {
            'something_else': 'who_cares2'
        }

        txs = [encode(tx).encode() for tx in [tx_2_1, tx_2_2]]
        expected_tree = merklize(txs)

        w = Wallet()

        input_hash = 'something2'
        signature = w.sign(expected_tree[0])

        expected_tree[1] = 'crap'

        sbc_2 = {
            'subblock': 1,
            'transactions': [tx_2_1, tx_2_2],
            'input_hash': input_hash,
            'signer': w.verifying_key,
            'merkle_tree': {
                'signature': signature,
                'leaves': expected_tree
            }
        }

        s = contender.SBCInbox()

        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
        loop.run_until_complete(s.process_message([sbc_1, sbc_2]))

        self.assertEqual(s.q, [])
