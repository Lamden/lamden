from lamden.nodes.hlc import HLC_Clock
from lamden.storage import BlockStorage, NonceStorage
from tests.unit.helpers.mock_blocks import generate_blocks
from unittest import TestCase
import os, copy

class TestNonce(TestCase):
    def setUp(self):
        self.nonces = NonceStorage()

    def tearDown(self):
        self.nonces.flush()

    def test_get_nonce_none_if_not_set_first(self):
        n = self.nonces.get_nonce(
            sender='test',
            processor='test2'
        )

        self.assertIsNone(n)

    def test_get_pending_nonce_none_if_not_set_first(self):
        n = self.nonces.get_pending_nonce(
            sender='test',
            processor='test2'
        )

        self.assertIsNone(n)

    def test_set_then_get_nonce_returns_set_nonce(self):
        self.nonces.set_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_set_then_get_pending_nonce_returns_set_pending_nonce(self):
        self.nonces.set_pending_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_pending_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_get_latest_nonce_zero_if_none_set(self):
        n = self.nonces.get_latest_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 0)

    def test_get_latest_nonce_returns_pending_nonce_if_not_none(self):
        self.nonces.set_pending_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_latest_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_get_latest_nonce_nonce_if_pending_nonce_is_none(self):
        self.nonces.set_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_latest_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

SAMPLE_BLOCK = {
    'number': 1,
    'hash': 'sample_block_hash',
    'hlc_timestamp': '1',
    'processed': {'hash': 'sample_tx_hash'}
}

class TestBlockStorage(TestCase):
    def setUp(self):
        self.bs = BlockStorage()
        self.hlc_clock = HLC_Clock()

    def tearDown(self):
        self.bs.flush()

    def test_creates_directories(self):
        self.assertTrue(self.bs.blocks_dir.is_dir())
        self.assertTrue(self.bs.blocks_alias_dir.is_dir())
        self.assertTrue(self.bs.txs_dir.is_dir())

    def test_flush(self):
        self.bs.flush()

        self.assertEqual(len(os.listdir(self.bs.blocks_dir)), 2)
        self.assertEqual(len(os.listdir(self.bs.txs_dir)), 0)
        self.assertEqual(len(os.listdir(self.bs.blocks_alias_dir)), 0)

    def test_store_block(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        block = generate_blocks(
            number_of_blocks=1,
            starting_block_num=0,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )[0]

        self.bs.store_block(copy.deepcopy(block))

        self.assertIsNotNone(self.bs.get_block(1))
        self.assertTrue(self.bs.blocks_dir.joinpath(str(block['number']).zfill(64)).is_file())
        self.assertTrue(self.bs.txs_dir.joinpath(block['processed'].get('hash')).is_file())
        self.assertTrue(self.bs.blocks_alias_dir.joinpath(block['hash']).is_symlink())
        self.assertTrue(self.bs.blocks_alias_dir.joinpath(block['hlc_timestamp']).is_symlink())

    def test_store_block_raises_if_no_or_malformed_tx(self):
        block = copy.deepcopy(SAMPLE_BLOCK)
        block['processed'] = {}

        self.assertRaises(ValueError, lambda: self.bs.store_block(block))

    def test_get_block(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        blocks = generate_blocks(
            number_of_blocks=3,
            starting_block_num=0,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )

        for block in blocks:
            self.bs.store_block(block)

        block_2 = self.bs.get_block(2)

        self.assertEqual(2, block_2.get('number'))

    def test_get_tx(self):
        block = copy.deepcopy(SAMPLE_BLOCK)
        self.bs.store_block(block)

        self.assertDictEqual(self.bs.get_tx(SAMPLE_BLOCK['processed']['hash']), SAMPLE_BLOCK['processed'])

    def test_get_later_blocks(self):
        blocks_1 = generate_blocks(
            number_of_blocks=3,
            starting_block_num=0,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks_1:
            self.bs.store_block(block)

        consensus_hlc = self.hlc_clock.get_new_hlc_timestamp()

        blocks_2 = generate_blocks(
            number_of_blocks=3,
            starting_block_num=blocks_1[2].get('number'),
            prev_block_hash=blocks_1[2].get('previous'),
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks_2:
            self.bs.store_block(block)

        later_blocks = self.bs.get_later_blocks(6, consensus_hlc)

        self.assertEqual(3, len(later_blocks))
        self.assertEqual(6, later_blocks[2].get('number'))
