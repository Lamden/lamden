from lamden.nodes.hlc import HLC_Clock
from lamden.utils import hlc
from lamden.storage import BlockStorage, NonceStorage, FSBlockDriver, FSHashStorageDriver, FSMemberHistory
from tests.unit.helpers.mock_blocks import generate_blocks, GENESIS_BLOCK
from unittest import TestCase
from lamden.crypto.wallet import Wallet

from pathlib import Path
import os, copy, time, random, shutil, json


class TestNonce(TestCase):
    def setUp(self):
        self.nonces = NonceStorage(root='/tmp')

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

    def test_safe_set__does_not_overwrite_higher_nonce_value(self):
        self.nonces.safe_set_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        self.nonces.safe_set_nonce(
            sender='test',
            processor='test2',
            value=1
        )

        n = self.nonces.get_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_safe_set__sets_higher_nonce_value(self):
        self.nonces.safe_set_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        self.nonces.safe_set_nonce(
            sender='test',
            processor='test2',
            value=3
        )

        n = self.nonces.get_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 3)

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
        self.temp_storage_dir = os.path.abspath("./.lamden")

        self.create_directories()
        self.bs = BlockStorage(root=str(self.temp_storage_dir))

        self.hlc_clock = HLC_Clock()

    def tearDown(self):
        if os.path.isdir(self.temp_storage_dir):
            shutil.rmtree(self.temp_storage_dir)

    def create_directories(self):
        if os.path.exists(Path(self.temp_storage_dir)):
            shutil.rmtree(Path(self.temp_storage_dir))

        os.makedirs(Path(self.temp_storage_dir))

    def test_creates_directories(self):
        self.assertTrue(self.bs.blocks_dir.is_dir())
        self.assertTrue(self.bs.blocks_alias_dir.is_dir())
        self.assertTrue(self.bs.txs_dir.is_dir())



    def test_flush(self):
        self.bs.flush()

        self.assertEqual(len(os.listdir(self.bs.blocks_dir)), 0)
        self.assertEqual(len(os.listdir(self.bs.txs_dir)), 0)
        self.assertEqual(len(os.listdir(self.bs.blocks_alias_dir)), 0)

    def test_METHOD_block_exists__returns_TRUE_if_block_exists(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        block = generate_blocks(
            number_of_blocks=1,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )[0]

        self.bs.store_block(copy.deepcopy(block))

        block_number = block.get('number')

        self.assertTrue(self.bs.block_exists(block_num=block_number))

    def test_METHOD_block_exists__returns_FALSE_if_block_does_NOT_exist(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        block = generate_blocks(
            number_of_blocks=1,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )[0]

        block_number = block.get('number')

        self.assertFalse(self.bs.block_exists(block_num=block_number))

    def test_store_block(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        block = generate_blocks(
            number_of_blocks=1,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )[0]

        self.bs.store_block(copy.deepcopy(block))

        block_number = block.get('number')
        block_res = self.bs.get_block(block_number)

        self.assertIsNotNone(block_res)

    def test_has_genesis_True(self):
        self.bs.store_block(copy.deepcopy(GENESIS_BLOCK))

        self.assertTrue(self.bs.has_genesis())

    def test_has_genesis_False(self):

        self.assertFalse(self.bs.has_genesis())

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

        self.assertEqual(hlc.nanos_from_hlc_timestamp(hlc_timestamp=block_2_hlc_timestamp), int(block_2.get('number')))

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

        prev_block = self.bs.get_previous_block(v=int(block_3_num))

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

        block_6_num = int(blocks[5].get('number'))
        high_block_num = block_6_num + 1

        prev_block = self.bs.get_previous_block(v=high_block_num)

        self.assertEqual(int(prev_block.get('number')), block_6_num)

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

    def test_METHOD_get_latest_block__returns_latest_block(self):
        blocks = generate_blocks(
            number_of_blocks=6,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks:
            self.bs.store_block(block)

        latest_block = self.bs.get_latest_block()
        self.assertDictEqual(blocks[5], latest_block)

    def test_METHOD_get_latest_block_number__returns_latest_block_number_as_int(self):
        blocks = generate_blocks(
            number_of_blocks=6,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks:
            self.bs.store_block(block)

        expected_result = int(blocks[-1].get('number'))

        latest_block_num = self.bs.get_latest_block_number()
        self.assertEqual(expected_result, latest_block_num)

    def test_METHOD_get_latest_block_number__returns_latest_block_hash(self):
        blocks = generate_blocks(
            number_of_blocks=6,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks:
            self.bs.store_block(block)

        expected_result = blocks[-1].get('hash')

        latest_block_hash = self.bs.get_latest_block_hash()
        self.assertEqual(expected_result, latest_block_hash)


class TestFSBlockDriver(TestCase):
    def setUp(self):
        self.test_dir = './.lamden'
        self.blocks_dir = 'blocks'
        self.blocks_path = os.path.join(self.test_dir, self.blocks_dir)

        self.create_directories()

        self.block_driver = FSBlockDriver(root=self.blocks_path)

    def tearDown(self):
        pass

    def create_directories(self):
        if os.path.exists(Path(self.test_dir)):
            shutil.rmtree(Path(self.test_dir))

        os.makedirs(Path(self.test_dir))
        os.makedirs(self.blocks_path)

    def create_block_num(self):
        zeros_pad_pre = '0' * 36
        zeros_pad_post = '0' * 9
        rand_int = random.randint(int(time.time()) - 2 * 365 * 24 * 60 * 60, int(time.time()))

        return f'{rand_int}{zeros_pad_post}'

    def create_block_filename(self):
        zeros_pad_pre = '0' * 36
        zeros_pad_post = '0' * 9
        rand_int = random.randint(int(time.time()) - 2 * 365 * 24 * 60 * 60, int(time.time()))

        return f'{zeros_pad_pre}{rand_int}{zeros_pad_post}'

    def create_block_files(self, num_files):
        for i in range(num_files):
            file_path = os.path.join(self.test_dir, 'blocks', f"{self.create_block_filename()}")
            open(file_path, 'w').close()

    def create_block_list(self, amount):
        block_list = set()

        while len(block_list) < amount:
            block_list.add(self.create_block_num())

        return [{'number': block_num} for block_num in block_list]

    def __is_block_file(self, filename):
        try:
            return os.path.isfile(os.path.join(self.blocks_path, filename)) and isinstance(int(filename), int)
        except:
            return False

    def test_INSTANCE_total_files__keeps_track_of_total_files(self):
        block_list = self.create_block_list(amount=5)
        self.block_driver.write_blocks(block_list=block_list)

        self.assertEqual(5, self.block_driver.total_files)

        block_list = self.create_block_list(amount=5)
        self.block_driver.write_blocks(block_list=block_list)

        self.assertEqual(10, self.block_driver.total_files)

    def test_INSTANCE_initialized__sets_initialized_on_startup(self):
        self.assertTrue(self.block_driver.initialized)

    def test_METHOD_get_file_path__can_retrieve_the_file_path_of_a_block(self):
        block_num = self.create_block_num()
        self.block_driver.write_block({
            'number': block_num
        })

        block_number_filled = str(block_num).zfill(64)
        file_path = self.block_driver.get_file_path(block_num=block_number_filled)

        # should not error
        f = open(file_path)

        self.assertIsNotNone(f)

    def test_METHOD_write_block__can_write_a_block(self):
        block_num = self.create_block_num()
        self.block_driver.write_block({
            'number': block_num
        })

        block = self.block_driver.find_block(block_num=block_num)

        self.assertEqual(int(block.get('number')), int(block_num))

    def test_METHOD_get_block__can_return_a_block(self):
        block_num = self.create_block_num()
        self.block_driver.write_block({
            'number': block_num
        })

        block = self.block_driver.find_block(block_num=block_num)

        self.assertIsNotNone(block)

    def test_METHOD_get_blocks__can_return_multiple_blocks(self):
        amount_of_blocks = 100
        block_list = self.create_block_list(amount=amount_of_blocks)

        self.block_driver.write_blocks(block_list)

        random_block_numbers = [block.get('number') for block in random.sample(block_list, 50)]

        blocks = self.block_driver.find_blocks(block_list=random_block_numbers)
        self.assertEqual(len(blocks), len(random_block_numbers))


        for block_num in random_block_numbers:
            list_of_found_block_numbers = [block.get('number') for block in blocks]
            self.assertTrue(block_num in list_of_found_block_numbers)

    def test_METHOD_find_next_block__returns_next_block(self):
        amount_of_blocks = 2000
        block_list = self.create_block_list(amount=amount_of_blocks)

        self.block_driver.write_blocks(block_list)

        block_list.sort(key=lambda x: int(x.get('number')))

        for index, block in enumerate(block_list):
            if index + 1 == amount_of_blocks:
                break

            next_block = self.block_driver.find_next_block(block_num=block_list[index].get('number'))

            expected_block_number = block_list[index + 1].get('number')

            self.assertEqual(int(expected_block_number), int(next_block.get('number')))

    def test_METHOD_find_next_blocks__returns_next_x_blocks(self):
        amount_of_blocks = 2000
        block_list = self.create_block_list(amount=amount_of_blocks)

        self.block_driver.write_blocks(block_list)

        block_list.sort(key=lambda x: int(x.get('number')))

        for index, block in enumerate(block_list):
            if index + 1 == amount_of_blocks:
                break

            next_block = self.block_driver.find_next_block(block_num=block_list[index].get('number'))

            expected_block_number = block_list[index + 1].get('number')

            self.assertEqual(int(expected_block_number), int(next_block.get('number')))


    def test_METHOD_find_previous_block__returns_previous_block(self):
        amount_of_blocks = 2000
        block_list = self.create_block_list(amount=amount_of_blocks)

        self.block_driver.write_blocks(block_list)

        block_list.sort(key=lambda x: int(x.get('number')))
        reversed_block_list = list(reversed(block_list))

        start_time = time.time()
        for index, block in enumerate(reversed_block_list):
            if index + 1 == amount_of_blocks:
                end_time = time.time()
                print({'start_time': start_time, 'end_time': end_time })
                break

            prev_block = self.block_driver.find_previous_block(block_num=block.get('number'))


            expected_block_number = reversed_block_list[index + 1].get('number')

            self.assertEqual(int(expected_block_number), int(prev_block.get('number')))

    def test_METHOD_find_previous_blocks__returns_next_x_blocks(self):
        amount_of_blocks = 2000
        block_list = self.create_block_list(amount=amount_of_blocks)

        self.block_driver.write_blocks(block_list)

        block_list.sort(key=lambda x: int(x.get('number')))

        for index, block in enumerate(reversed(block_list)):
            if index + 1 == amount_of_blocks:
                break

            previous_block = self.block_driver.find_next_block(block_num=block_list[index].get('number'))

            expected_block_number = block_list[index + 1].get('number')

            self.assertEqual(int(expected_block_number), int(previous_block.get('number')))

    def test_METHOD_get_total_blocks__returns_proper_amount_of_blocks(self):
        amount_of_blocks = 5
        block_list = self.create_block_list(amount=amount_of_blocks)

        self.block_driver.write_blocks(block_list=block_list)
        start_time = time.time()
        num_of_blocks = self.block_driver.get_total_blocks()
        end_time = time.time()

        total_time = end_time - start_time

        print({'start_time': start_time, 'end_time': end_time, 'total_time': total_time})

        self.assertEqual(amount_of_blocks, num_of_blocks)

    def test_METHOD_block_exists__returns_False_if_no_block(self):
        block_exists = self.block_driver.block_exists(block_num=25)

        self.assertFalse(block_exists)

    def test_METHOD_block_exists__returns_False_if_no_block(self):
        amount_of_blocks = 1
        block_list = self.create_block_list(amount=amount_of_blocks)
        block = block_list[0]
        self.block_driver.write_block(block=block)

        block_exists = self.block_driver.block_exists(block_num=block.get('number'))

        self.assertTrue(block_exists)

    def test_METHOD_find_next_block__returns_genesis_if_provided_neg_one(self):
        self.block_driver.write_block(block=GENESIS_BLOCK)

        genesis_block = self.block_driver.find_next_block(block_num=-1)

        self.assertEqual(0, int(genesis_block.get("number")))

    def test_METHOD_find_next_block__returns_prev_block_if_provided_out_of_high_range(self):
        self.block_driver.write_block(block=GENESIS_BLOCK)

        genesis_block = self.block_driver.find_previous_block(block_num="9999999999999999999999999999")

        self.assertEqual(0, int(genesis_block.get("number")))

    def test_read_speed_vs_legacy(self):
        print(" ")
        print("--- NEW DRIVER")
        amount_of_blocks = 500
        block_list = self.create_block_list(amount=amount_of_blocks)

        self.block_driver.write_blocks(block_list)

        block_list.sort(key=lambda x: int(x.get('number')))

        new_start_time = time.time()
        for index, block in enumerate(block_list):
            if index + 1 == amount_of_blocks:
                new_end_time = time.time()
                print({
                    'start_time': new_start_time,
                    'end_time': new_end_time,
                    'sec_taken': new_end_time - new_start_time
                })
                break

            next_block = self.block_driver.find_next_block(block_num=block_list[index].get('number'))

            expected_block_number = block_list[index + 1].get('number')

            self.assertEqual(int(expected_block_number), int(next_block.get('number')))

        print()
        print("--- LEGACY METHOD")

        self.create_directories()

        for block in block_list:
            block_num = block.get('number')

            with open(os.path.join(self.blocks_path, str(block_num).zfill(64)), 'w') as f:
                f.write(json.dumps(block))

        legacy_start_time = time.time()
        for index, block in enumerate(block_list):
            if index + 1 == amount_of_blocks:
                legacy_end_time = time.time()
                print({
                    'start_time': legacy_start_time,
                    'end_time': legacy_end_time,
                    'sec_taken': legacy_end_time - legacy_start_time
                })
                break

            curr_block_num = block_list[index].get('number')
            v = int(curr_block_num)

            all_blocks = [int(name) for name in os.listdir(self.blocks_path) if self.__is_block_file(name)]
            later_blocks = list(filter(lambda block_num: block_num > v, all_blocks))

            later_blocks.sort()
            next_block_num = str(later_blocks[0]).zfill(64)

            f = open(os.path.join(self.blocks_path, next_block_num))
            encoded_block = f.read()
            next_block = json.loads(encoded_block)
            f.close()

            expected_block_number = block_list[index + 1].get('number')
            self.assertEqual(int(expected_block_number), int(next_block.get('number')))

        new_total_time = new_end_time - new_start_time
        new_legacy_time = legacy_end_time - legacy_start_time

        self.assertGreater(new_legacy_time, new_total_time)

    def test_METOHD__traverse_up__returns_None_if_no_next_dir_at_root(self):
        amount_of_blocks = 1
        block_list = self.create_block_list(amount=amount_of_blocks)
        block = block_list[0]
        block_num = str(block.get('number')).zfill(64)
        self.block_driver.write_block(block=block)
        dir_path = self.block_driver.get_file_path(block_num=block_num)

        dir = self.block_driver._traverse_up(current_directory=dir_path, direction='next')

        self.assertIsNone(dir)

    def test_METOHD__traverse_down__returns_None_if_no_next_dir_at_root(self):
        amount_of_blocks = 1
        block_list = self.create_block_list(amount=amount_of_blocks)
        block = block_list[0]
        block_num = str(block.get('number')).zfill(64)
        self.block_driver.write_block(block=block)
        dir_path = self.block_driver.get_file_path(block_num=block_num)

        dir = self.block_driver._traverse_up(current_directory=dir_path, direction='previous')

        self.assertIsNone(dir)

    def test_METHOD_delete_block__removes_a_block_file(self):
        block_num = self.create_block_num().zfill(64)

        self.block_driver.write_block({
            'number': block_num
        })

        file_path = self.block_driver.get_file_path(block_num=block_num)

        self.assertTrue(os.path.exists(file_path))

        self.block_driver.delete_block(block_num=block_num)

        self.assertFalse(os.path.exists(file_path))

    def test_METHOD_delete_block__removes_file_dir_remains_if_other_files_exist_in_same_dir(self):
        block_num = self.create_block_num()
        block_num_2 = str(int(block_num) + 1).zfill(64)
        block_num_1 = block_num.zfill(64)

        # Write block 1
        self.block_driver.write_block({
            'number': block_num_1
        })
        file_path_1 = self.block_driver.get_file_path(block_num=block_num_1)
        self.assertTrue(os.path.exists(file_path_1))

        # Write block 2
        self.block_driver.write_block({
            'number': block_num_2
        })
        file_path_2 = self.block_driver.get_file_path(block_num=block_num_2)
        self.assertTrue(os.path.exists(file_path_2))

        # Delete block 1
        self.block_driver.delete_block(block_num=block_num_1)

        # Assert block 1 gone
        self.assertFalse(os.path.exists(file_path_1))

        # Assert block 2 exists
        self.assertTrue(os.path.exists(file_path_2))

    def test_PROVATE_METHOD_remove_empty_dirs__removed_a_dir_tree_to_root(self):
        block_num = self.create_block_num().zfill(64)
        file_path = self.block_driver.get_file_path(block_num=block_num)
        starting_path = os.path.dirname(file_path)

        # Create directory structure
        os.makedirs(starting_path)
        self.assertTrue(os.path.exists(starting_path))

        self.block_driver._remove_empty_dirs(starting_dir=starting_path)

        # Removed all the way to root
        top_level = starting_path
        for i in range(3):
            top_level = os.path.dirname(top_level)
            self.assertFalse(os.path.exists(top_level))

    def test_PROVATE_METHOD_remove_empty_dirs__removes_no_directories_if_files_exist(self):
        block_num = self.create_block_num().zfill(64)
        self.block_driver.write_block({
            'number': block_num
        })

        file_path = self.block_driver.get_file_path(block_num=block_num)
        starting_path = os.path.dirname(file_path)

        self.assertTrue(os.path.exists(starting_path))

        self.block_driver._remove_empty_dirs(starting_dir=starting_path)

        # Removed all the way to root
        self.assertTrue(os.path.exists(file_path))

    def test_PROVATE_METHOD_remove_empty_dirs__stop_when_multiple_sub_dirs_exist(self):
        block_num = self.create_block_num().zfill(64)
        file_path = self.block_driver.get_file_path(block_num=block_num)
        starting_path = os.path.dirname(file_path)

        # Create directory structure
        os.makedirs(starting_path)
        self.assertTrue(os.path.exists(starting_path))

        # Add another sub directory into the tree
        new_dir = os.path.join(os.path.dirname(file_path), "testing")
        os.makedirs(new_dir)
        self.assertTrue(os.path.exists(new_dir))

        self.block_driver._remove_empty_dirs(starting_dir=starting_path)

        # Removed all the way to root
        self.assertTrue(os.path.exists(new_dir))

class TestFSHashStorageDriver(TestCase):
    def setUp(self):
        self.test_dir = './.lamden'
        self.txs_dir = 'txs'
        self.txs_path = os.path.join(self.test_dir, self.txs_dir)
        self.alias_dir = 'block_alias'
        self.alias_path = os.path.join(self.test_dir, self.alias_dir)

        self.transactions_driver = FSHashStorageDriver(root=self.txs_path)
        self.alias_driver = FSHashStorageDriver(root=self.alias_path)

        self.create_directories()

    def tearDown(self):
        pass

    def create_directories(self):
        if os.path.exists(Path(self.test_dir)):
            shutil.rmtree(Path(self.test_dir))

        os.makedirs(Path(self.test_dir))
        os.makedirs(self.txs_path)
        os.makedirs(self.alias_path)

    def test_METHOD_write_file__can_write_file_to_proper_directory(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'

        tx_data = {
            'hash': tx_hash
        }

        self.transactions_driver.write_file(
            hash_str = tx_hash,
            data = tx_data
        )

        file_path = os.path.join(self.txs_path, tx_hash[:2], tx_hash[2:4], tx_hash[4:6], tx_hash)
        self.assertTrue(os.path.exists(file_path))

    def test_METHOD_get_file__can_retrieve_a_file(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'

        tx_data = {
            'hash': tx_hash
        }

        self.transactions_driver.write_file(
            hash_str = tx_hash,
            data = tx_data
        )

        tx = self.transactions_driver.get_file(tx_hash)

        self.assertIsNotNone(tx)

    def test_METHOD_get_file__returns_None_if_file_not_exist(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'
        tx = self.transactions_driver.get_file(tx_hash)

        self.assertIsNone(tx)

    def test_METHOD_get_file__can_retrieve_a_file(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'

        tx_data = {
            'hash': tx_hash
        }

        self.transactions_driver.write_file(
            hash_str = tx_hash,
            data = tx_data
        )

        tx = self.transactions_driver.get_file(tx_hash)

        self.assertIsNotNone(tx)

    def test_METHOD_write_symlink__can_write_a_symlink(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'
        alias_hash = 'fcf68695ed53d23939d5f82198cc61d7fbf20837f69c16b963f1dc9e0162a5c2'

        self.transactions_driver.write_file(
            hash_str=tx_hash,
            data={}
        )

        tx_path = os.path.join(self.transactions_driver.get_directory(hash_str=tx_hash), tx_hash)

        self.alias_driver.write_symlink(
            hash_str=alias_hash,
            link_to=tx_path
        )

        alias_path = os.path.join(self.alias_driver.get_directory(hash_str=alias_hash), alias_hash)
        self.assertTrue(os.path.islink(alias_path))


    def test_METHOD_get_file__can_retrieve_a_file_from_link(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'
        alias_hash = 'fcf68695ed53d23939d5f82198cc61d7fbf20837f69c16b963f1dc9e0162a5c2'

        self.transactions_driver.write_file(hash_str=tx_hash, data={})
        tx_path = os.path.join(self.transactions_driver.get_directory(hash_str=tx_hash), tx_hash)

        self.alias_driver.write_symlink(hash_str=alias_hash, link_to=tx_path)

        tx_file = self.alias_driver.get_file(hash_str=alias_hash)

        self.assertIsNotNone(tx_file)

    def test_METHOD_is_syslink_valid__True(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'
        alias_hash = 'fcf68695ed53d23939d5f82198cc61d7fbf20837f69c16b963f1dc9e0162a5c2'

        self.transactions_driver.write_file(hash_str=tx_hash, data={})
        tx_path = os.path.join(self.transactions_driver.get_directory(hash_str=tx_hash), tx_hash)

        self.alias_driver.write_symlink(hash_str=alias_hash, link_to=tx_path)

        valid = self.alias_driver.is_symlink_valid(hash_str=alias_hash)

        self.assertTrue(valid)

    def test_METHOD_is_syslink_valid__False(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'
        alias_hash = 'fcf68695ed53d23939d5f82198cc61d7fbf20837f69c16b963f1dc9e0162a5c2'

        tx_path = os.path.join(self.transactions_driver.get_directory(hash_str=tx_hash), tx_hash)

        self.alias_driver.write_symlink(hash_str=alias_hash, link_to=tx_path)

        valid = self.alias_driver.is_symlink_valid(hash_str=alias_hash)

        self.assertFalse(valid)

    def test_METHOD_remove_syslink(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'
        alias_hash = 'fcf68695ed53d23939d5f82198cc61d7fbf20837f69c16b963f1dc9e0162a5c2'

        self.transactions_driver.write_file(hash_str=tx_hash, data={})
        tx_path = os.path.join(self.transactions_driver.get_directory(hash_str=tx_hash), tx_hash)

        self.alias_driver.write_symlink(hash_str=alias_hash, link_to=tx_path)

        self.alias_driver.remove_symlink(hash_str=alias_hash)
        link_dir = os.path.join(self.alias_driver.get_directory(hash_str=alias_hash), alias_hash)

        self.assertFalse(os.path.exists(link_dir))

    def test_METHOD_remove_syslink__returns_if_not_exists(self):
        alias_hash = 'fcf68695ed53d23939d5f82198cc61d7fbf20837f69c16b963f1dc9e0162a5c2'
        self.alias_driver.remove_symlink(hash_str=alias_hash)

    def test_PRIVATE_METHOD_remove_empty_dirs_to_root(self):
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'
        dir_path = self.transactions_driver.get_directory(hash_str=tx_hash)

        os.makedirs(dir_path)

        self.assertTrue(os.path.exists(dir_path))
        self.transactions_driver.delete_file(hash_str=tx_hash)

        check_dir = dir_path
        for i in range(3):
            self.assertFalse(os.path.exists(check_dir))
            check_dir = os.path.dirname(check_dir)

        # root still exists
        self.assertTrue(os.path.exists(check_dir))

class TestFSMemberHistory(TestCase):
    def setUp(self):
        self.test_dir = './.lamden'
        self.member_history_dir = 'member_history'
        self.member_history_path = os.path.join(self.test_dir, self.member_history_dir)

        self.wallet = Wallet()

        self.member_history = FSMemberHistory(root=self.member_history_path, wallet=self.wallet)

        self.create_directories()

    def tearDown(self):
        pass

    def create_directories(self):
        if os.path.exists(Path(self.test_dir)):
            shutil.rmtree(Path(self.test_dir))

        os.makedirs(Path(self.test_dir))

    def test_INSTANCE__can_create_instance(self):
        self.assertIsInstance(self.member_history, FSMemberHistory)

        self.assertEqual(os.path.abspath(self.member_history_path), self.member_history.root)
        self.assertEqual(self.wallet, self.member_history.wallet)

    def test_METHOD_save_members_list_can_save_list(self):
        block_num = '1689708055238093056'
        member_list = [Wallet().verifying_key, Wallet().verifying_key, Wallet().verifying_key]

        self.member_history.set(block_num=block_num, members_list=member_list)

        path_to_file = self.member_history.get_file_path(block_num=block_num.zfill(64))

        f = open(os.path.join(path_to_file))
        encoded_data = f.read()
        data = json.loads(encoded_data)
        f.close()

        self.assertEqual(member_list, data.get('members'))
        self.assertEqual(block_num, data.get('number'))
        self.assertIsNotNone(data.get('signature'))

    def test_METHOD_get_members_list__can_return_members_list_from_block_number(self):
        block_num = '1689708055238093056'
        member_list = [Wallet().verifying_key, Wallet().verifying_key, Wallet().verifying_key]

        self.member_history.set(block_num=block_num, members_list=member_list)

        member_list_retrieved = self.member_history.get(block_num=int(block_num) + 1)

        self.assertEqual(member_list, member_list_retrieved)

    def test_METHOD_get_members_list__returns_empty_list_if_no_prev_data(self):
        block_num = '1689708055238093056'

        member_list_retrieved = self.member_history.get(block_num=int(block_num) + 1)

        self.assertEqual([], member_list_retrieved)

    def test_METHOD_verify_member__can_lookup_members_and_verify_vk_is_IN_list(self):
        block_num = '1689708055238093056'
        test_member = Wallet().verifying_key
        member_list = [test_member, Wallet().verifying_key, Wallet().verifying_key]
        self.member_history.set(block_num=block_num, members_list=member_list)

        self.assertTrue(self.member_history.verify_member(block_num=int(block_num) + 1, vk=test_member))

    def test_METHOD_verify_member__can_lookup_members_and_verify_vk_is_NOT_in_list(self):
        block_num = '1689708055238093056'
        test_member = Wallet().verifying_key
        member_list = [Wallet().verifying_key, Wallet().verifying_key, Wallet().verifying_key]
        self.member_history.set(block_num=block_num, members_list=member_list)

        self.assertFalse(self.member_history.verify_member(block_num=int(block_num) + 1, vk=test_member))

    def test_METHOD_verify_member__returns_FALSE_if_no_block_num_provided(self):
        self.assertFalse(self.member_history.verify_member(vk=Wallet().verifying_key))

    def test_METHOD_verify_member__returns_FALSE_if_no_vk_provided(self):
        self.assertFalse(self.member_history.verify_member(block_num='1689708055238093056'))

    def test_METHOD_verify_member__returns_false_if_not_signed_by_caller(self):
        block_num = '1689708055238093056'
        test_member = Wallet().verifying_key
        member_list = [test_member, Wallet().verifying_key, Wallet().verifying_key]
        self.member_history.set(block_num=block_num, members_list=member_list)

        self.member_history.wallet = Wallet()

        self.assertFalse(self.member_history.verify_member(block_num=int(block_num) + 1, vk=test_member))

    def test_METHOD_set_secure__sets_wallet(self):
        member_history = FSMemberHistory(root=self.member_history_path)

        self.assertIsNone(member_history.wallet)

        wallet = Wallet()
        member_history.set_secure(wallet=wallet)

        self.assertEqual(wallet, member_history.wallet)

    def test_METHOD_purge__can_purge_history(self):
        block_nums = ['1689708055238093056', '1689708055238093057', '1689708055238093058']

        member_list = [Wallet().verifying_key, Wallet().verifying_key, Wallet().verifying_key]

        # set and assert history is created
        for block_num in block_nums:
            self.member_history.set(block_num=block_num, members_list=member_list)
            self.assertIsNotNone(self.member_history.get(block_num=block_num))

        self.member_history.purge()

        # assert history is gone
        for block_num in block_nums:
            self.assertEqual([], self.member_history.get(block_num=block_num))

    def test_METHOD_has_history__returns_TRUE_if_HAS_history(self):
        block_num = '1689708055238093056'
        member_list = [Wallet().verifying_key, Wallet().verifying_key, Wallet().verifying_key]
        self.member_history.set(block_num=block_num, members_list=member_list)

        self.assertTrue(self.member_history.has_history())

    def test_METHOD_has_history__returns_TRUE_if_HAS_history(self):
        self.assertFalse(self.member_history.has_history())