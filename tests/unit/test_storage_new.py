from lamden.nodes.hlc import HLC_Clock
from lamden.utils import hlc
from lamden.storage import BlockStorage, NonceStorage
from tests.unit.helpers.mock_blocks import generate_blocks
from unittest import TestCase
import os, copy
from pathlib import Path
import shutil


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
        self.temp_storage_dir = Path.cwd().joinpath('temp_storage')
        try:
            shutil.rmtree(self.temp_storage_dir)
        except FileNotFoundError:
            pass

        self.temp_storage_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.bs = BlockStorage(root=Path.cwd().joinpath('temp_storage'))
        except Exception as err:
            print(err)

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
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )[0]

        self.bs.store_block(copy.deepcopy(block))

        block_number = block.get('number')

        self.assertIsNotNone(self.bs.get_block(block_number))
        self.assertTrue(self.bs.blocks_dir.joinpath(str(block['number']).zfill(64)).is_file())
        self.assertTrue(self.bs.txs_dir.joinpath(block['processed'].get('hash')).is_file())
        self.assertTrue(self.bs.blocks_alias_dir.joinpath(block['hash']).is_symlink())

    def test_store_block_raises_if_no_or_malformed_tx(self):
        block = copy.deepcopy(SAMPLE_BLOCK)
        block['processed'] = {}

        self.assertRaises(ValueError, lambda: self.bs.store_block(block))

    def test_get_block_by_block_number(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        blocks = generate_blocks(
            number_of_blocks=3,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )

        for block in blocks:
            self.bs.store_block(block)

        block_2_hlc_timestamp = blocks[1].get('hlc_timestamp')
        block_2 = self.bs.get_block(hlc.nanos_from_hlc_timestamp(hlc_timestamp=block_2_hlc_timestamp))

        self.assertEqual(hlc.nanos_from_hlc_timestamp(hlc_timestamp=block_2_hlc_timestamp), block_2.get('number'))

    def test_get_block__by_hcl_timestamp(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        blocks = generate_blocks(
            number_of_blocks=3,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )

        for block in blocks:
            self.bs.store_block(block)

        block_2_hlc_timestamp = blocks[1].get('hlc_timestamp')
        block_2 = self.bs.get_block(v=block_2_hlc_timestamp)

        self.assertEqual(block_2_hlc_timestamp, block_2.get('hlc_timestamp'))

    def test_get_block__None_returns_None(self):
        block_2 = self.bs.get_block(v=None)
        self.assertIsNone(block_2)

    def test_get_block__invalid_hlc_returns_none(self):
        block_2 = self.bs.get_block(v="1234")
        self.assertIsNone(block_2)

    def test_get_block__neg_block_num_returns_none(self):
        block_2 = self.bs.get_block(v=-1)
        self.assertIsNone(block_2)

    def test_get_tx(self):
        block = copy.deepcopy(SAMPLE_BLOCK)
        self.bs.store_block(block)

        self.assertDictEqual(self.bs.get_tx(SAMPLE_BLOCK['processed']['hash']), SAMPLE_BLOCK['processed'])

    def test_get_later_blocks(self):
        blocks_1 = generate_blocks(
            number_of_blocks=3,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks_1:
            self.bs.store_block(block)

        consensus_hlc = self.hlc_clock.get_new_hlc_timestamp()

        blocks_2 = generate_blocks(
            number_of_blocks=3,
            prev_block_hash=blocks_1[2].get('previous'),
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks_2:
            self.bs.store_block(block)

        later_blocks = self.bs.get_later_blocks(hlc_timestamp=consensus_hlc)

        self.assertEqual(3, len(later_blocks))

    def test_get_previous_block__by_block_number(self):
        blocks = generate_blocks(
            number_of_blocks=6,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks:
            self.bs.store_block(block)

        block_2_num = blocks[1].get('number')
        block_3_num = blocks[2].get('number')

        prev_block = self.bs.get_previous_block(v=block_3_num)

        self.assertEqual(prev_block.get('number'), block_2_num)

    def test_get_previous_block__by_hlc_timestamp(self):
        blocks = generate_blocks(
            number_of_blocks=6,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks:
            self.bs.store_block(block)

        block_2_hlc_timestamp = blocks[1].get('hlc_timestamp')
        block_3_hlc_timestamp = blocks[2].get('hlc_timestamp')

        prev_block = self.bs.get_previous_block(v=block_3_hlc_timestamp)

        self.assertEqual(prev_block.get('hlc_timestamp'), block_2_hlc_timestamp)

    def test_get_previous_block__high_block_num_returns_lastest_block(self):
        blocks = generate_blocks(
            number_of_blocks=6,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks:
            self.bs.store_block(block)

        block_6_num = blocks[5].get('number')
        high_block_num = block_6_num + 1

        prev_block = self.bs.get_previous_block(v=high_block_num)

        self.assertEqual(prev_block.get('number'), block_6_num)

    def test_get_previous_block__None_returns_None(self):
        prev_block = self.bs.get_previous_block(v=None)
        self.assertIsNone(prev_block)

    def test_get_previous_block__zero_block_num_returns_None(self):
        prev_block = self.bs.get_previous_block(v=0)
        self.assertIsNone(prev_block)

    def test_get_previous_block__neg_block_num_returns_None(self):
        prev_block = self.bs.get_previous_block(v=-1)
        self.assertIsNone(prev_block)

    def test_get_previous_block__returns_None_if_no_earlier_blocks(self):
        prev_block = self.bs.get_previous_block(v="2022-07-18T17:04:54.967101696Z_0")
        self.assertIsNone(prev_block)

    def test_set_previous_hash__can_set_hash_in_block(self):
        blocks = generate_blocks(
            number_of_blocks=6,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks:
            prev_hash = block.get('hash')
            self.bs.store_block(block)

        hlc_timestamp = self.hlc_clock.get_new_hlc_timestamp()
        next_block = {
            'previous': '0' * 64,
            'hash': '0' * 64,
            'hlc_timestamp': hlc_timestamp,
            'number': hlc.nanos_from_hlc_timestamp(hlc_timestamp)
        }

        self.bs.set_previous_hash(block=next_block)

        self.assertEqual(prev_hash, next_block.get('previous'))

    def test_remove_block_alias(self):
        blocks = generate_blocks(
            number_of_blocks=1,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks:
            block_hash = block.get('hash')
            self.bs.store_block(block)

        self.bs._BlockStorage__remove_block_alias(block_hash=block_hash)

        file_path = os.path.join(self.bs.blocks_alias_dir, block_hash)

        self.assertFalse(os.path.isfile(file_path))

