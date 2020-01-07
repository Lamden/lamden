from unittest import TestCase

from cilantro_ee.nodes.masternode.block_contender import Aggregator, CurrentContenders, SBCInbox, \
    SBCInvalidSignatureError, SBCBlockHashMismatchError, SBCMerkleLeafVerificationError

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
        s = SBCInbox(MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender)

        self.assertFalse(s.sbc_is_valid(sbc))

    def test_verify_sbc_false_invalid_sig(self):
        s = SBCInbox(MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender, idx=0, poisoned_sig=b'\x00' * 64)

        with self.assertRaises(SBCInvalidSignatureError):
            s.sbc_is_valid(sbc)

    def test_verify_sbc_false_prev_block_hash_ne_curr_block_hash(self):
        s = SBCInbox(MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'B' * 32, w=sender)

        with self.assertRaises(SBCBlockHashMismatchError):
            s.sbc_is_valid(sbc=sbc)

    def test_verify_sbc_false_sbc_merkle_leave_does_not_verify(self):
        s = SBCInbox(MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender, poison_result_hash=True)

        with self.assertRaises(SBCMerkleLeafVerificationError):
            s.sbc_is_valid(sbc=sbc)

    def test_verify_sbc_false_tx_hash_not_in_merkle_leaves(self):
        s = SBCInbox(MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender, poison_tx=True)

        with self.assertRaises(SBCMerkleLeafVerificationError):
            s.sbc_is_valid(sbc=sbc)

    def test_verify_sbc_true_if_no_failures(self):
        s = SBCInbox(MetaDataStorage(), socket_id=_socket('tcp://127.0.0.1:8888'), ctx=zmq.asyncio.Context())

        input_hash = secrets.token_bytes(32)

        sender = Wallet()

        sbc = random_txs.sbc_from_txs(input_hash, b'\x00'*32, w=sender)

        s.sbc_is_valid(sbc=sbc)
