from unittest import TestCase
from cilantro_ee.nodes.masternode.block_contender import SubBlockGroup
from cilantro_ee.storage.vkbook import VKBook
import secrets


def random_wallets(n=10):
    return [secrets.token_hex(32) for _ in range(n)]


class TestSubBlockGroup(TestCase):
    def test_init(self):
        SubBlockGroup(0, 'A'*64)

    def test_consensus_not_reached_after_init(self):
        contacts = VKBook(delegates=['A'*64], masternodes=['A'*64])
        s = SubBlockGroup(0, 'A'*64, contacts=contacts)

        self.assertFalse(s.is_consensus_reached())

    def test_current_quorum_reached_is_zero_if_best_result_has_less_than_min_quorum(self):
        contacts = VKBook(delegates=['A' * 64, 'B' * 64, 'C' * 64], masternodes=['A' * 64],
                          num_boot_del=3)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        s.best_rh = 'B'*64

        s.rh[s.best_rh] = {'A'*64}

        self.assertEqual(s.get_current_quorum_reached(), 0)

    def test_current_quorum_reached_is_max_quorum_if_best_result_has_max_quorum_votes(self):
        contacts = VKBook(delegates=['A' * 64, 'B' * 64, 'C' * 64], masternodes=['A' * 64],
                          num_boot_del=3)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        s.best_rh = 'B' * 64

        s.rh[s.best_rh] = {'A' * 64, 'B' * 64, 'C' * 64}

        self.assertEqual(s.get_current_quorum_reached(), s.max_quorum)

    def test_current_quorum_reached_is_max_quorum_if_best_result_has_more_than_max_quorum_votes(self):
        contacts = VKBook(delegates=['A' * 64, 'B' * 64, 'C' * 64, 'D' * 64], masternodes=['A' * 64],
                          num_boot_del=3)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        s.best_rh = 'B' * 64

        s.rh[s.best_rh] = {'A' * 64, 'B' * 64, 'C' * 64, 'D' * 64}

        self.assertEqual(s.get_current_quorum_reached(), s.max_quorum)

    def test_current_quorum_returns_zero_when_no_result_has_enough_votes(self):
        contacts = VKBook(delegates=['A' * 64, 'B' * 64, 'C' * 64, 'D' * 64], masternodes=['A' * 64],
                          num_boot_del=3)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        s.best_rh = 'B' * 64
        another_result = 'C' * 64

        s.rh[s.best_rh] = {'A' * 64}
        s.rh[another_result] = {'B' * 64}

        self.assertEqual(s.get_current_quorum_reached(), 0)

    def test_current_quorum_returns_leading_vote_number_if_reduced_quorum_can_be_set(self):
        delegates = random_wallets(100)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        s.best_rh = 'B' * 64
        another_result = 'C' * 64

        s.rh[s.best_rh] = set(delegates[:59])
        s.rh[another_result] = {'B' * 64}

        self.assertEqual(s.get_current_quorum_reached(), 59)

    def test_consensus_is_possible_returns_false_when_no_result_has_quorum(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        s.best_rh = 1
        s.rh[1] = {'B' * 64}
        s.rh[2] = {'B' * 64}
        s.rh[3] = {'B' * 64}
        s.rh[4] = {'B' * 64}
        s.rh[5] = {'B' * 64}
        s.rh[6] = {'B' * 64}
        s.rh[7] = {'B' * 64}
        s.rh[8] = {'B' * 64}
        s.rh[9] = {'B' * 64}
        s.rh[0] = {'B' * 64}

        self.assertFalse(s.is_consensus_possible())

    def test_consensus_is_possible_returns_true_when_a_single_result_has_max_quorum(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        s.best_rh = 1
        s.rh[1] = {'B' * 64, 'C' * 64, 'D' * 64, 'E' * 64, 'F' * 64, '0' * 64, '1' * 64}
        s.rh[2] = {'B' * 64}

        self.assertTrue(s.is_consensus_possible())

    def test_consensus_is_possible_if_there_are_still_enough_votes_left_to_make_quorum(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        s.best_rh = 1
        s.rh[1] = {'B' * 64, 'C' * 64, 'D' * 64, 'E' * 64, 'F' * 64, '0' * 64}
        s.rh[2] = {'B' * 64, 'C' * 64, 'D' * 64}

        self.assertTrue(s.is_consensus_possible())

    def test_add_sbc(self):
        pass
