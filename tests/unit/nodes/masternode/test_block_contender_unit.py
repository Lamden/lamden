from unittest import TestCase
from cilantro_ee.nodes.masternode.block_contender import SubBlockGroup
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.core.crypto.wallet import Wallet
import secrets
from tests import random_txs


def random_wallets(n=10):
    return [secrets.token_hex(32) for _ in range(n)]

class TestSubBlockGroup(TestCase):
    def test_init(self):
        SubBlockGroup(0, 'A' * 64)

    def test_consensus_not_reached_after_init(self):
        contacts = VKBook(delegates=['A' * 64], masternodes=['A' * 64])
        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        self.assertFalse(s.is_consensus_reached())

    def test_current_quorum_reached_is_zero_if_best_result_has_less_than_min_quorum(self):
        contacts = VKBook(delegates=['A' * 64, 'B' * 64, 'C' * 64], masternodes=['A' * 64],
                          num_boot_del=3)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        s.best_rh = 'B' * 64

        s.rh[s.best_rh] = {'A' * 64}

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

    def test_get_input_hashes_returns_list_of_hashes_in_group(self):
        pass

    def test_get_merkle_leaves_returns_empty_list_if_no_best_rh(self):
        pass

    # *** #

    def test_verify_sbc_false_sender_ne_merkle_proof_signer(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender)

        self.assertFalse(s._verify_sbc(sender_vk=Wallet().verifying_key(), sbc=sbc))

    def test_verify_sbc_false_sbc_idx_ne_self_sb_idx(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender, idx=2)

        self.assertFalse(s._verify_sbc(sender_vk=sender.verifying_key(), sbc=sbc))

    def test_verify_sbc_false_invalid_sig(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender, idx=0, poisoned_sig=b'\x00' * 64)

        self.assertFalse(s._verify_sbc(sender_vk=sender.verifying_key(), sbc=sbc))

    def test_verify_sbc_false_prev_block_hash_ne_curr_block_hash(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'B' * 32, w=sender)

        self.assertFalse(s._verify_sbc(sender_vk=sender.verifying_key(), sbc=sbc))

    def test_verify_sbc_false_sbc_merkle_leave_does_not_verify(self):
        pass

    def test_verify_sbc_false_tx_hash_not_in_merkle_leaves(self):
        pass

    def test_verify_sbc_false_sb_idx_gte_num_sb_per_block(self):
        pass

    def test_verify_sbc_true_if_no_failures(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender)

        self.assertTrue(s._verify_sbc(sender_vk=sender.verifying_key(), sbc=sbc))
