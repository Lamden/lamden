from unittest import TestCase

from cilantro_ee.nodes.masternode.block_contender import Aggregator, CurrentContenders, SBCInbox
from cilantro_ee.crypto.wallet import Wallet
from tests import random_txs
from cilantro_ee.storage import MetaDataStorage
from cilantro_ee.sockets.services import _socket
import secrets

import zmq.asyncio

def random_wallets(n=10):
    return [secrets.token_hex(32) for _ in range(n)]


class TestSBCInbox(TestCase):
    def test_verify_sbc_false_sender_ne_merkle_proof_signer(self):
        delegates = random_wallets(10)

        s = SBCInbox(MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender)

        self.assertFalse(s.sbc_is_valid(sbc))

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