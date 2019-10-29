from unittest import TestCase
from cilantro_ee.nodes.masternode.block_contender import SubBlockGroup
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.core.crypto.wallet import Wallet
import secrets
from tests import random_txs
from collections import namedtuple

from cilantro_ee.core.messages.capnp_impl import capnp_struct as schemas
import os
import capnp

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

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
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, 'A' * 64, contacts=contacts)

        SBCInput = namedtuple('SBCInput', ['inputHash'])

        s.sender_to_sbc = {
            delegates[0]: SBCInput(b'A' * 32),
            delegates[1]: SBCInput(b'B' * 32),
            delegates[2]: SBCInput(b'C' * 32),
            delegates[3]: SBCInput(b'D' * 32),
            delegates[4]: SBCInput(b'E' * 32),
        }

        expected = [b'A' * 32, b'B' * 32, b'C' * 32, b'D' * 32, b'E' * 32]

        self.assertEqual(set(s.get_input_hashes()), set(expected))

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
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender, poison_result_hash=True)

        self.assertFalse(s._verify_sbc(sender_vk=sender.verifying_key(), sbc=sbc))

    def test_verify_sbc_false_tx_hash_not_in_merkle_leaves(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender, poison_tx=True)

        self.assertFalse(s._verify_sbc(sender_vk=sender.verifying_key(), sbc=sbc))

    def test_verify_sbc_false_sb_idx_gte_num_sb_per_block(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(200, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender, idx=200)

        self.assertFalse(s._verify_sbc(sender_vk=sender.verifying_key(), sbc=sbc))

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

    def test_get_sbc_builds_best_sb_and_returns(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender)

        s.best_rh = sbc.resultHash
        s.rh[s.best_rh] = {sbc}

        got_sbc = s.get_sb()

        self.assertEqual(sbc.resultHash, got_sbc.merkleRoot)
        self.assertEqual(sbc.subBlockIdx, got_sbc.subBlockIdx)
        self.assertEqual(sbc.inputHash, got_sbc.inputHash)
        self.assertEqual(sbc.signature, got_sbc.signatures[0])
        self.assertListEqual([leaf for leaf in sbc.merkleLeaves],
                             [leaf for leaf in got_sbc.merkleLeaves])

    def test_get_ordered_transactions_returns_properly(self):
        SBCMockTXs = namedtuple('SBCMockTXs', ['transactions'])

        best_sbc = SBCMockTXs(transactions=(1, 2, 3, 4, 5))

        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        s.best_rh = b'B' * 32
        s.rh[s.best_rh] = {best_sbc}

        txs = s._get_ordered_transactions()

        self.assertEqual((1, 2, 3, 4, 5), txs)

    def test_get_merkle_leaves_returns_properly(self):
        SBCMockMerkle = namedtuple('SBCMockMerkle', ['merkleLeaves'])

        best_sbc = SBCMockMerkle(merkleLeaves=(1, 2, 3, 4, 5))

        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        s.best_rh = b'B' * 32
        s.rh[s.best_rh] = {best_sbc}

        txs = s._get_merkle_leaves()

        self.assertEqual((1, 2, 3, 4, 5), txs)

    def test_get_merkle_leaves_returns_empty_list_if_no_best_rh(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        self.assertListEqual(s._get_merkle_leaves(), [])

    def test_is_empty_returns_true_if_no_merkle_leaves(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        self.assertTrue(s.is_empty())

    def test_is_empty_returns_false_if_merkle_leaves(self):
        SBCMockMerkle = namedtuple('SBCMockMerkle', ['merkleLeaves'])

        best_sbc = SBCMockMerkle(merkleLeaves=(1, 2, 3, 4, 5))

        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        s.best_rh = b'B' * 32
        s.rh[s.best_rh] = {best_sbc}

        self.assertFalse(s.is_empty())

    def test_add_sbc_returns_none_if_cannot_verify(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender, poison_tx=True)

        self.assertFalse(s.add_sbc(sender.verifying_key(), sbc))

    def test_add_sbc_sender_already_exists_overwrites_with_new_sbc(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc_1 = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender)
        sbc_2 = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender)

        s.add_sbc(sender.verifying_key(), sbc_1)

        self.assertEqual(s.sender_to_sbc[sender.verifying_key()], sbc_1)

        s.add_sbc(sender.verifying_key(), sbc_2)

        self.assertEqual(s.sender_to_sbc[sender.verifying_key()], sbc_2)

    def test_add_sbc_adds_map_of_sender_vk_to_sbc(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc_1 = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender)

        s.add_sbc(sender.verifying_key(), sbc_1)

        self.assertEqual(s.sender_to_sbc[sender.verifying_key()], sbc_1)

    def test_add_sbc_adds_to_result_hash_set(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc_1 = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender)

        s.add_sbc(sender.verifying_key(), sbc_1)

        self.assertEqual(s.rh[sbc_1.resultHash], {sbc_1})

# (self.best_rh is None) or (len(self.rh[sbc.resultHash]) > len(self.rh[self.best_rh]))

    def test_add_sbc_best_rh_none_sets_best_to_submitted(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc_1 = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender)

        s.add_sbc(sender.verifying_key(), sbc_1)

        self.assertEqual(s.best_rh, sbc_1.resultHash)

    def test_add_sbc_added_result_hash_set_gt_current_best_rh_sets_best_rh_to_submitted(self):
        delegates = random_wallets(10)

        contacts = VKBook(delegates=delegates,
                          masternodes=['A' * 64],
                          num_boot_del=10)

        s = SubBlockGroup(0, b'A' * 32, contacts=contacts)

        input_hash = secrets.token_bytes(32)

        sender_1 = Wallet()
        sender_2 = Wallet()

        sbc_1, sbc_2 = random_txs.double_sbc_from_tx(input_hash, s.curr_block_hash, w1=sender_1, w2=sender_2)

        sender_3 = Wallet()

        sbc_3 = random_txs.sbc_from_txs(input_hash, s.curr_block_hash, w=sender_3)

        s.add_sbc(sender_3.verifying_key(), sbc_3)

        self.assertEqual(s.best_rh, sbc_3.resultHash)

        s.add_sbc(sender_2.verifying_key(), sbc_2)

        self.assertEqual(s.best_rh, sbc_3.resultHash)

        s.add_sbc(sender_1.verifying_key(), sbc_1)

        self.assertEqual(s.best_rh, sbc_2.resultHash)

    def test_tx_hashes_added_to_transaction_hash_to_tx_object(self):
        pass