from unittest import TestCase
from cilantro_ee.storage.contract import BlockchainDriver
import secrets
import os
import capnp
from tests import random_txs

from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
from cilantro_ee.core.nonces import PENDING_NONCE_KEY, NONCE_KEY

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
signal_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/signals.capnp')


class TestCompleteDriver(TestCase):
    def setUp(self):
        self.db = BlockchainDriver()
        self.db.flush()

    def tearDown(self):
        self.db.flush()

    def test_init(self):
        self.assertIsNotNone(self.db)

    def test_set_latest_block_hash_not_64_chars(self):
        bhash = b'a' * 6
        with self.assertRaises(AssertionError):
            self.db.set_latest_block_hash(bhash)

    def test_set_latest_block_hash_not_hex_fails(self):
        bhash = 'x' * 32
        with self.assertRaises(ValueError):
            self.db.set_latest_block_hash(bhash)

    def test_set_latest_block_hash_returns_when_successful(self):
        bhash = b'a' * 32

        self.db.set_latest_block_hash(bhash)

    def test_get_latest_block_hash_none(self):
        expected = b'\00' * 32

        got = self.db.get_latest_block_hash()

        self.assertEqual(expected, got)

    def test_get_latest_block_hash_after_setting(self):
        expected = b'a' * 32

        self.db.set_latest_block_hash(expected)

        got = self.db.get_latest_block_hash()

        self.assertEqual(expected, got)

    def test_latest_block_hash_as_property(self):
        expected = b'a' * 32

        self.db.latest_block_hash = expected

        got = self.db.latest_block_hash

        self.assertEqual(expected, got)

    def test_set_latest_block_num_not_number(self):
        num = 'a'
        with self.assertRaises(ValueError):
            self.db.set_latest_block_num(num)

    def test_set_latest_block_num_negative_fails(self):
        num = -1000
        with self.assertRaises(AssertionError):
            self.db.set_latest_block_num(num)

    def test_set_latest_block_num_returns_when_successful(self):
        num = 64

        self.db.set_latest_block_num(num)

    def test_get_latest_block_num_none(self):
        got = self.db.get_latest_block_num()

        self.assertEqual(0, got)

    def test_get_latest_block_num_after_setting(self):
        num = 64

        self.db.set_latest_block_num(num)

        got = self.db.get_latest_block_num()

        self.assertEqual(num, got)

    def test_get_latest_block_num_as_property(self):
        num = 64

        self.db.latest_block_num = num

        got = self.db.latest_block_num

        self.assertEqual(num, got)

    def test_update_nonce_empty_hash_adds_anything(self):
        sender = b'123'
        processor = b'456'
        tx_payload = transaction_capnp.TransactionPayload.new_message(
            sender=sender,
            processor=processor,
            nonce=999,
        )

        nonces = {}
        self.db.update_nonce_hash(nonces, tx_payload)

        self.assertEqual(nonces.get((b'456', b'123')), 1000)

    def test_update_nonce_when_new_max_nonce_found(self):
        nonces = {}

        sender = b'123'
        processor = b'456'
        tx_payload = transaction_capnp.TransactionPayload.new_message(
            sender=sender,
            processor=processor,
            nonce=999,
        )

        self.db.update_nonce_hash(nonces, tx_payload)

        sender = b'123'
        processor = b'456'
        tx_payload = transaction_capnp.TransactionPayload.new_message(
            sender=sender,
            processor=processor,
            nonce=1000,
        )

        self.db.update_nonce_hash(nonces, tx_payload)

        self.assertEqual(nonces.get((b'456', b'123')), 1001)

    def test_update_nonce_only_keeps_max_values(self):
        nonces = {}

        sender = b'123'
        processor = b'456'
        tx_payload = transaction_capnp.TransactionPayload.new_message(
            sender=sender,
            processor=processor,
            nonce=1000,
        )

        self.db.update_nonce_hash(nonces, tx_payload)

        sender = b'123'
        processor = b'456'
        tx_payload = transaction_capnp.TransactionPayload.new_message(
            sender=sender,
            processor=processor,
            nonce=999,
        )

        self.db.update_nonce_hash(nonces, tx_payload)

        self.assertEqual(nonces.get((b'456', b'123')), 1001)

    def test_update_nonce_keeps_multiple_nonces(self):
        nonces = {}

        sender = b'123'
        processor = b'456'
        tx_payload = transaction_capnp.TransactionPayload.new_message(
            sender=sender,
            processor=processor,
            nonce=1000,
        )

        self.db.update_nonce_hash(nonces, tx_payload)

        sender = b'124'
        processor = b'456'
        tx_payload = transaction_capnp.TransactionPayload.new_message(
            sender=sender,
            processor=processor,
            nonce=999,
        )

        self.db.update_nonce_hash(nonces, tx_payload)

        self.assertEqual(nonces.get((b'456', b'123')), 1001)
        self.assertEqual(nonces.get((b'456', b'124')), 1000)

    def test_nonces_are_set_and_deleted_from_commit_nonces(self):
        n1 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n2 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n3 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n4 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n5 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n6 = (secrets.token_bytes(32), secrets.token_bytes(32))

        nonces = {
            n1: 5,
            n3: 3,
            n5: 6,
            n6: 100
        }

        self.db.set_pending_nonce(n1[0], n1[1], 5)
        self.db.set_pending_nonce(n2[0], n2[1], 999)
        self.db.set_pending_nonce(n3[0], n3[1], 3)
        self.db.set_pending_nonce(n4[0], n4[1], 888)
        self.db.set_pending_nonce(n5[0], n5[1], 6)

        self.db.set_nonce(n1[0], n1[1], 4)
        self.db.set_nonce(n3[0], n3[1], 2)
        self.db.set_nonce(n5[0], n5[1], 5)

        self.assertEqual(len(self.db.iter(PENDING_NONCE_KEY)), 5)
        self.assertEqual(len(self.db.iter(NONCE_KEY)), 3)

        self.db.commit_nonces(nonce_hash=nonces)

        self.assertEqual(len(self.db.iter(PENDING_NONCE_KEY)), 2)
        self.assertEqual(len(self.db.iter(NONCE_KEY)), 4)

    def test_delete_pending_nonce_removes_all_pending_nonce_but_not_normal_nonces(self):
        self.db.set_pending_nonce(processor=secrets.token_bytes(32),
                                  sender=secrets.token_bytes(32),
                                  nonce=100)

        self.db.set_pending_nonce(processor=secrets.token_bytes(32),
                                  sender=secrets.token_bytes(32),
                                  nonce=100)

        self.db.set_pending_nonce(processor=secrets.token_bytes(32),
                                  sender=secrets.token_bytes(32),
                                  nonce=100)

        self.db.set_pending_nonce(processor=secrets.token_bytes(32),
                                  sender=secrets.token_bytes(32),
                                  nonce=100)

        self.db.set_pending_nonce(processor=secrets.token_bytes(32),
                                  sender=secrets.token_bytes(32),
                                  nonce=100)

        self.db.set_nonce(processor=secrets.token_bytes(32),
                          sender=secrets.token_bytes(32),
                          nonce=100)

        self.assertEqual(len(self.db.iter(PENDING_NONCE_KEY)), 5)
        self.assertEqual(len(self.db.iter(NONCE_KEY)), 1)

        self.db.delete_pending_nonces()

        self.assertEqual(len(self.db.iter(PENDING_NONCE_KEY)), 0)
        self.assertEqual(len(self.db.iter(NONCE_KEY)), 1)

    def test_commit_nonce_when_nonce_hash_is_none_that_it_commits_all_current_pending_nonces(self):
        n1 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n2 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n3 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n4 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n5 = (secrets.token_bytes(32), secrets.token_bytes(32))
        n6 = (secrets.token_bytes(32), secrets.token_bytes(32))

        self.db.set_pending_nonce(processor=n1[0], sender=n1[1], nonce=100)
        self.db.set_pending_nonce(processor=n2[0], sender=n2[1], nonce=100)
        self.db.set_pending_nonce(processor=n3[0], sender=n3[1], nonce=100)
        self.db.set_pending_nonce(processor=n4[0], sender=n4[1], nonce=100)
        self.db.set_pending_nonce(processor=n5[0], sender=n5[1], nonce=100)

        self.db.set_nonce(processor=n6[0], sender=n6[1], nonce=100)

        self.assertEqual(len(self.db.iter(PENDING_NONCE_KEY)), 5)
        self.assertEqual(len(self.db.iter(NONCE_KEY)), 1)

        self.db.commit_nonces()

        self.assertEqual(len(self.db.iter(PENDING_NONCE_KEY)), 0)
        self.assertEqual(len(self.db.iter(NONCE_KEY)), 6)

        self.assertEqual(self.db.get_nonce(processor=n1[0], sender=n1[1]), 100)
        self.assertEqual(self.db.get_nonce(processor=n2[0], sender=n2[1]), 100)
        self.assertEqual(self.db.get_nonce(processor=n3[0], sender=n3[1]), 100)
        self.assertEqual(self.db.get_nonce(processor=n4[0], sender=n4[1]), 100)
        self.assertEqual(self.db.get_nonce(processor=n5[0], sender=n5[1]), 100)

    def test_update_nonces_with_block(self):
        block = random_txs.random_block(txs=20)

        self.db.update_nonces_with_block(block)

        nonces = self.db.iter(NONCE_KEY)

        self.assertEqual(len(nonces), 20)

        vals = []
        for n in nonces:
            vals.append(self.db.get(n))

        self.assertEqual(sorted(vals), list(range(1, 21)))
