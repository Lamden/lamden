from contracting import config
from contracting.db.driver import ContractDriver, FSDriver
from contracting.db.encoder import encode, decode
from contracting.stdlib.bridge.decimal import ContractingDecimal
from lamden.logger.base import get_logger
from lamden.utils import hlc
import os
import pathlib
import shutil
import json

LATEST_BLOCK_HASH_KEY = '__latest_block.hash'
LATEST_BLOCK_HEIGHT_KEY = '__latest_block.height'
STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')
BLOCK_0 = {
    'number': 0,
    'hash': '0' * 64
}


class BlockStorage:
    def __init__(self, root=None, block_diver=None):
        self.log = get_logger('BlockStorage')
        self.root = pathlib.Path(root) if root is not None else STORAGE_HOME
        self.block_driver = block_diver or LayeredDirectoryDriver(root=self.root)
        self.blocks_dir = self.root.joinpath('blocks')
        self.blocks_alias_dir = self.blocks_dir.joinpath('alias')
        self.txs_dir = self.blocks_dir.joinpath('txs')

        self.__build_directories()
        self.log.info(f'Initialized block & tx storage at \'{self.root}\', {self.total_blocks()} existing blocks found.')

    def __build_directories(self):
        self.root.mkdir(exist_ok=True, parents=True)
        self.blocks_dir.mkdir(exist_ok=True, parents=True)
        self.blocks_alias_dir.mkdir(exist_ok=True, parents=True)
        self.txs_dir.mkdir(exist_ok=True, parents=True)

    def __cull_tx(self, block):
        # Pops all transactions from the block and replaces them with the hash only for storage space
        # Returns the data and hashes for storage in a different folder. Block is modified in place
        tx = block.get('processed', None)
        tx_hash = tx.get('hash', None)
        block['processed'] = tx_hash

        return tx, tx_hash

    def __write_block(self, block):
        num = block.get('number')

        if type(num) == dict:
            num = num.get('__fixed__')
            block['number'] = num

        name = str(num).zfill(64)

        hash_symlink_name = block.get('hash')

        encoded_block = encode(block)
        with open(self.blocks_dir.joinpath(name), 'w') as f:
            f.write(encoded_block)

        try:
            os.symlink(self.blocks_dir.joinpath(name), self.blocks_alias_dir.joinpath(hash_symlink_name))
        except FileExistsError as err:
            self.log.debug(err)

    def __write_tx(self, tx_hash, tx):
        with open(self.txs_dir.joinpath(tx_hash), 'w') as f:
            encoded_tx = encode(tx)
            f.write(encoded_tx)

    def __fill_block(self, block):
        tx_hash = block.get('processed')
        tx = self.get_tx(tx_hash)
        block['processed'] = tx

    def __is_block_file(self, filename):
        try:
            return os.path.isfile(os.path.join(self.blocks_dir, filename)) and isinstance(int(filename), int)
        except:
            return False

    def __remove_block_alias(self, block_hash: str):
        file_path = os.path.join(self.blocks_alias_dir, block_hash)

        if not os.path.isfile(file_path):
            return

        attempts = 0
        while os.path.isfile(file_path) and attempts < 100:
            try:
                os.remove(file_path)
            except Exception:
                pass

            attempts += 1

        if os.path.isfile(file_path):
            self.log.error(f'Could not remove block alias {file_path}')

    def is_genesis_block(self, block):
        return block.get('genesis', None) is not None

    def total_blocks(self):
        return len([name for name in os.listdir(self.blocks_dir) if os.path.isfile(os.path.join(self.blocks_dir, name))])

    def flush(self):
        if self.blocks_dir.is_dir():
            shutil.rmtree(self.blocks_dir)
        if self.txs_dir.is_dir():
            shutil.rmtree(self.txs_dir)
        if self.blocks_alias_dir.is_dir():
            shutil.rmtree(self.blocks_alias_dir)

        self.__build_directories()
        self.log.debug(f'Flushed block & tx storage at \'{self.root}\'')

    def store_block(self, block):
        if not self.is_genesis_block(block=block):
            tx, tx_hash = self.__cull_tx(block)

            if tx is None or tx_hash is None:
                raise ValueError('Block has no transaction information or malformed tx data.')

            self.__write_tx(tx_hash, tx)

        self.__write_block(block)


    def get_block(self, v=None):
        if v is None:
            return None

        if isinstance(v, str) and hlc.is_hcl_timestamp(hlc_timestamp=v):
            nanos = hlc.nanos_from_hlc_timestamp(hlc_timestamp=v)
            if nanos > 0:
                v = nanos

        try:
            if isinstance(v, int):
                f = open(self.blocks_dir.joinpath(str(v).zfill(64)))
            else:
                f = open(self.blocks_alias_dir.joinpath(v))
        except Exception as err:
            self.log.error(f'Block \'{v}\' was not found: {err}')
            return None

        encoded_block = f.read()
        block = decode(encoded_block)

        if not self.is_genesis_block(block=block):
            self.__fill_block(block)

        f.close()

        return block

    def get_previous_block(self, v):
        if not v:
            return None

        if hlc.is_hcl_timestamp(hlc_timestamp=v):
            v = hlc.nanos_from_hlc_timestamp(hlc_timestamp=v)
        else:
            if not isinstance(v, int) or v < 0:
                return None

        all_blocks = [int(name) for name in os.listdir(self.blocks_dir) if self.__is_block_file(name)]
        earlier_blocks = list(filter(lambda block_num: block_num < v, all_blocks))

        if len(earlier_blocks) == 0:
            return None

        earlier_blocks.sort()
        prev_block = earlier_blocks[-1]

        return self.get_block(v=prev_block)

    def get_next_block(self, v):
        if hlc.is_hcl_timestamp(hlc_timestamp=v):
            v = hlc.nanos_from_hlc_timestamp(hlc_timestamp=v)
        else:
            if not isinstance(v, int):
                v = -1

        all_blocks = [int(name) for name in os.listdir(self.blocks_dir) if self.__is_block_file(name)]
        later_blocks = list(filter(lambda block_num: block_num > v, all_blocks))

        if len(later_blocks) == 0:
            return None

        later_blocks.sort()
        next_block = later_blocks[0]

        return self.get_block(v=next_block)

    def get_tx(self, h):
        try:
            f = open(self.txs_dir.joinpath(h))
            encoded_tx = f.read()

            tx = decode(encoded_tx)

            f.close()
        except FileNotFoundError as err:
            self.log.error(err)
            tx = None

        return tx

    def get_later_blocks(self, hlc_timestamp):
        starting_block_num = hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp)
        all_blocks = [int(name) for name in os.listdir(self.blocks_dir) if self.__is_block_file(name)]
        later_blocks = list(filter(lambda block_num: block_num > starting_block_num, all_blocks))
        later_blocks.sort()
        return [self.get_block(v=block_num) for block_num in later_blocks]

    def set_previous_hash(self, block: dict):
        current_previous_block_hash = block.get('previous')
        previous_block = self.get_previous_block(v=int(block.get('number')))

        new_previous_block_hash = previous_block.get('hash')
        block['previous'] = new_previous_block_hash

        block_exists = self.get_block(v=current_previous_block_hash)

        if not block_exists:
            self.__remove_block_alias(block_hash=current_previous_block_hash)


# TODO: remove pending nonces if we end up getting rid of them.
# TODO: move to component responsible for state maintenance.
NONCE_FILENAME = '__n'
PENDING_NONCE_FILENAME = '__pn'
class NonceStorage:
    def __init__(self, root=None):
        root = root if root is not None else STORAGE_HOME
        self.driver = FSDriver(root=root)

    # Move this to transaction.py
    def get_nonce(self, sender, processor):
        return self.driver.get(NONCE_FILENAME + config.INDEX_SEPARATOR + sender + config.DELIMITER + processor)

    # Move this to transaction.py
    def get_pending_nonce(self, sender, processor):
        return self.driver.get(PENDING_NONCE_FILENAME + config.INDEX_SEPARATOR + sender + config.DELIMITER + processor)

    def set_nonce(self, sender, processor, value):
        self.driver.set(
            NONCE_FILENAME + config.INDEX_SEPARATOR + sender + config.DELIMITER + processor,
            value
        )

    def set_pending_nonce(self, sender, processor, value):
        self.driver.set(
            PENDING_NONCE_FILENAME + config.INDEX_SEPARATOR + sender + config.DELIMITER + processor,
            value
        )

    # Move this to webserver.py
    def get_latest_nonce(self, sender, processor):
        latest_nonce = self.get_pending_nonce(sender=sender, processor=processor)

        if latest_nonce is None:
            latest_nonce = self.get_nonce(sender=sender, processor=processor)

        if latest_nonce is None:
            latest_nonce = 0

        return latest_nonce

    def get_next_nonce(self, sender, processor):
        current_nonce = self.get_pending_nonce(sender=sender, processor=processor)

        if current_nonce is None:
            current_nonce = self.get_nonce(sender=sender, processor=processor)

        if current_nonce is None:
            return 0

        return current_nonce + 1

    def flush(self):
        self.driver.flush_file(NONCE_FILENAME)
        self.driver.flush_file(PENDING_NONCE_FILENAME)

    def flush_pending(self):
        self.driver.flush_file(PENDING_NONCE_FILENAME)

# TODO: move to component responsible for state maintenance.
def get_latest_block_hash(driver: ContractDriver):
    latest_hash = driver.get(LATEST_BLOCK_HASH_KEY)
    if latest_hash is None:
        return '0' * 64
    return latest_hash

# TODO: move to component responsible for state maintenance.
def set_latest_block_hash(h, driver: ContractDriver):
    driver.set(LATEST_BLOCK_HASH_KEY, h)

# TODO: move to component responsible for state maintenance.
def get_latest_block_height(driver: ContractDriver):
    h = driver.get(LATEST_BLOCK_HEIGHT_KEY, save=False)
    if h is None:
        return -1

    if type(h) == ContractingDecimal:
        h = int(h._d)

    return int(h)

class BlockDriver:
    def find_block(self):
        # This method will take a block number and return that block and the next x amount of blocks
        raise NotImplementedError("Subclasses must implement this method.")

    def find_blocks(self):
        # This method will take a block number and return that block and the next x amount of blocks
        raise NotImplementedError("Subclasses must implement this method.")

    def write_block(self):
        # This method will take a block number and return that block and the next x amount of blocks
        raise NotImplementedError("Subclasses must implement this method.")

    def write_blocks(self):
        # This method will take a block number and return that block and the next x amount of blocks
        raise NotImplementedError("Subclasses must implement this method.")

    def find_previous_block(self, block_num: str):
        # This method will take a block number and return the previous block
        raise NotImplementedError("Subclasses must implement this method.")

    def find_next_block(self, block_num: str):
        # This method will take a block number and return the next block
        raise NotImplementedError("Subclasses must implement this method.")

import os
import json
import shutil

class LayeredDirectoryDriver:
    def __init__(self, root):
        self.root = root
        self.time_units = [
            31_536_000_000_000_000,  # year
            2_592_000_000_000_000,   # month
            604_800_000_000_000,     # week
            86_400_000_000_000,      # day
            3_600_000_000_000,       # hour
            60_000_000_000           # minute
        ]

    def _find_directories(self, block_num):
        directories = []
        for unit in self.time_units:
            lower_bound = (block_num // unit) * unit
            upper_bound = lower_bound + unit - 1
            dir_name = f"{lower_bound}_{upper_bound}"
            directories.append(dir_name)
            block_num %= unit
        return directories

    def _get_directories_in_path(self, dir_tree_list):
        current_path = os.path.join(self.root, *dir_tree_list)
        current_directories = [entry.name for entry in os.scandir(current_path) if entry.is_dir()]
        current_directories.sort()
        return current_directories

    def _get_files_in_path(self, dir_tree_list):
        current_path = os.path.join(self.root, *dir_tree_list)
        files = [entry.name for entry in os.scandir(current_path) if entry.is_file()]
        files.sort()
        return files

    def _get_next_directory(self, dir_tree_list):
        if not dir_tree_list:
            return self._get_directories_in_path(dir_tree_list)[:1]

        current_directories = self._get_directories_in_path(dir_tree_list[:-1])
        current_dir = dir_tree_list[-1]
        index = current_directories.index(current_dir)

        if index + 1 < len(current_directories):
            return dir_tree_list[:-1] + [current_directories[index + 1]]
        else:
            return self._get_next_directory(dir_tree_list[:-1])

    def _get_file_path(self, block_num):
        directories = self._find_directories(block_num)
        file_path = os.path.join(self.root, *directories, str(block_num))
        return file_path

    def write_block(self, block: dict):
        block_num = int(block.get('number'))
        file_path = self._get_file_path(block_num)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w') as f:
            json.dump(block, f)


    def write_blocks(self, block_list):
        for block in block_list:
            self.write_block(block)

    def move_block(self, src_file, block_num):
        src_path = str(src_file)
        dst_path = self._get_file_path(block_num)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.move(src_path, dst_path)

    def find_previous_block(self, block_num):
        block_num = int(block_num)
        current_dirs = self._find_directories(block_num)
        files = self._get_files_in_path(current_dirs)

        previous_file = None
        for file in map(int, files):
            if file < block_num:
                previous_file = file
            else:
                break

        return str(previous_file) if previous_file is not None else None

    def find_next_block(self, block_num):
        block_num = int(block_num)
        current_dirs = self._find_directories(block_num)
        current_path = os.path.join(self.root, *current_dirs)
        files_in_current_dir = self._get_files_in_path(current_dirs)

        # Find the next block in the current directory
        for file in map(int, files_in_current_dir):
            if file > block_num:
                return file

        # If the next block is not in the current directory, search in the next directories
        next_dirs = self._get_next_directory(current_dirs)
        while next_dirs and next_dirs != current_dirs:
            files_in_next_dir = self._get_files_in_path(next_dirs)
            if files_in_next_dir:
                return int(files_in_next_dir[0])

            next_dirs = self._get_next_directory(next_dirs)
            # Break the loop if there are no more directories to search
            if next_dirs == current_dirs[:-1]:
                break

        return None
    
    def find_blocks(self, block_num, amount_of_block):
        block_num = int(block_num)
        current_dirs = self._find_directories(block_num)
        files = self._get_files_in_path(current_dirs)

        result_files = []
        for file in map(int, files):
            if file >= block_num:
                result_files.append(str(file))
                if len(result_files) == amount_of_block:
                    break

        return result_files

    def find_block(self, block_num):
        blocks = self.find_blocks(block_num=block_num, amount_of_block=1)

        try:
            return blocks[0]
        except IndexError:
            return None


'''
class LayeredDirectoryDriver(BlockDriver):
    # This driver stores the blocks in directories determined by a time structure based on the block number because
    # Block numbers are a nanosecond representation of am HLC timestamp.
    # This storage method scales the time required to search for "next" or "previous" blocks and doesn't require reading
    # in all current blocks to do so.

    def __init__(self, root):
        self.root = root
        self.minute = 60_000_000_000
        self.hour = 3_600_000_000_000
        self.day = 86_400_000_000_000
        self.week = 604_800_000_000_000
        self.month = 2_592_000_000_000_000
        self.year = 31_536_000_000_000_000

    def _find_directories(self, block_num: int):
        dir_levels = [self.year, self.month, self.week, self.day, self.hour, self.minute]
        directories = []
        for level in dir_levels:
            lower_bound = (block_num // level) * level
            upper_bound = lower_bound + level - 1
            dir_name = "{}_{}".format(lower_bound, upper_bound)
            directories.append(dir_name)
            block_num %= level
        return directories

    def _has_directories(self, dir_tree_list: list):
        current_directory = os.path.join(self.root, *dir_tree_list)
        directory_contents = os.listdir(current_directory)

        for index, item in enumerate(directory_contents):
            if os.path.isfile(item):
                directory_contents.pop(index)

        return len(directory_contents) > 0

    def _get_directories_in_path(self, dir_tree_list: list):
        current_path = os.path.join(self.root, *dir_tree_list)
        current_directories = os.listdir(current_path)

        # Remove files from traversal
        for index, item in enumerate(current_directories):
            item_path = os.path.join(current_path, item)
            if os.path.isfile(item_path):
                current_directories.pop(index)

        current_directories.sort()
        return current_directories

    def _decend_dir_tree(self, dir_tree_list):
        while self._has_directories(dir_tree_list=dir_tree_list):
            current_path = os.path.join(self.root, *dir_tree_list)
            current_directories = os.listdir(current_path)

            for index, item in enumerate(current_directories):
                if os.path.isfile(os.path.join(current_path, item)):
                    current_directories.pop(index)

            dir_tree_list.append(current_directories[0])

        return dir_tree_list

    def _get_next_directory(self, dir_tree_list: list):
        if len(dir_tree_list) == 0:
            current_directories = self._get_directories_in_path(dir_tree_list=dir_tree_list)
            for index, dir_name in enumerate(current_directories):
                if dir_name == dir_tree_list[len(dir_tree_list) - 1]:
                    dir_tree_list.pop()
                    try:
                        dir_tree_list.append(current_directories[index + 1])
                    except IndexError:
                        return None
                    dir_tree_list = self._decend_dir_tree(dir_tree_list)
                    return self._get_next_directory(dir_tree_list)
        else:
            last_item = dir_tree_list.pop()

        current_path = os.path.join(self.root, *dir_tree_list)
        current_directories = os.listdir(current_path)


        # Remove files from traversal
        for index, item in enumerate(current_directories):
            if os.path.isfile(os.path.join(current_path, item)):
                current_directories.pop(index)

        current_directories = self._get_directories_in_path(dir_tree_list=dir_tree_list)

        if len(current_directories) > 1:
            for index, dir_name in enumerate(current_directories):
                ## START HERE
                if dir_name == last_item:
                    try:
                        next_dir = current_directories[index + 1]
                    except IndexError:
                        dir_tree_list.pop()
                        dir_tree_list.append(dir_name)
                        return dir_tree_list

            return None
        else:
            return self._get_next_directory(dir_tree_list)


    def get_file_path(self, block_num: str):
        input_number = int(block_num)
        current_dirs = self._find_directories(input_number)
        file_path = os.path.join(self.root, *current_dirs, block_num)
        return file_path

    def write_block(self, block: dict):
        block_num = block.get('number')
        file_path = self.get_file_path(block_num)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w') as f:
            json.dump(block, f)

    def write_blocks(self, block_list: list):
        for block in block_list:
            self.write_block(block=block)

    def move_block(self, src_file, block_num: str):
        src_path = str(src_file)
        dst_path = self.get_file_path(block_num)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.move(src_path, dst_path)

    def find_previous_block(self, block_num: str):
        input_number = int(block_num)
        current_dirs = self._find_directories(input_number)
        search_dir = os.path.join(self.root, *current_dirs)

        files_in_dir = os.listdir(search_dir)
        numeric_files = sorted([int(file) for file in files_in_dir if file.isdigit()])

        previous_file = None
        for file in numeric_files:
            if file < input_number:
                previous_file = file
            else:
                break

        return str(previous_file) if previous_file is not None else None

    def find_next_block(self, block_num: str):
        input_number = int(block_num)
        current_dirs = self._find_directories(input_number)

        next_file = None
        while next_file is None:
            search_dir = os.path.join(self.root, *current_dirs)

            files_in_dir = os.listdir(search_dir)
            numeric_files = sorted([int(file) for file in files_in_dir if file.isdigit()])

            for index, file in enumerate(numeric_files):
                if file > input_number:
                    next_file = file
                    break

                if index == len(numeric_files) - 1:
                    current_dirs = self._get_next_directory(dir_tree_list=current_dirs)
                    if current_dirs is None:
                        break

        return str(next_file) if next_file is not None else None

    def find_blocks(self, block_num, amount_of_block):
        input_number = int(block_num)
        current_dirs = self._find_directories(input_number)
        search_dir = os.path.join(self.root, *current_dirs)

        files_in_dir = os.listdir(search_dir)
        numeric_files = sorted([int(file) for file in files_in_dir if file.isdigit()])

        result_files = []
        for file in numeric_files:
            if file >= input_number:
                result_files.append(str(file))
                if len(result_files) == amount_of_block:
                    break

        return result_files

    def find_block(self, block_num):
        blocks = self.find_blocks(block_num=block_num, amount_of_block=1)

        try:
            return blocks[0]
        except IndexError:
            return None
'''

# TODO: move to component responsible for state maintenance.
def set_latest_block_height(h, driver: ContractDriver):
    driver.set(LATEST_BLOCK_HEIGHT_KEY, int(h))

# TODO: implement and move to component responsible for state maintenance.
def update_state_with_transaction(tx, driver: ContractDriver, nonces: NonceStorage):
    raise NotImplementedError
    #nonces_to_delete = []

    #if tx['state'] is not None and len(tx['state']) > 0:
    #    for delta in tx['state']:
    #        driver.set(delta['key'], delta['value'])

    #        nonces.set_nonce(
    #            sender=tx['transaction']['payload']['sender'],
    #            processor=tx['transaction']['payload']['processor'],
    #            value=tx['transaction']['payload']['nonce'] + 1
    #        )

    #        nonces_to_delete.append((tx['transaction']['payload']['sender'], tx['transaction']['payload']['processor']))

    #for n in nonces_to_delete:
    #    nonces.set_pending_nonce(*n, value=None)

# TODO: implement and move to component responsible for state maintenance.
def update_state_with_block(block, driver: ContractDriver, nonces: NonceStorage, set_hash_and_height=True):
    raise NotImplementedError
    #if block.get('subblocks') is not None:
    #    for sb in block['subblocks']:
    #        for tx in sb['transactions']:
    #            update_state_with_transaction(tx, driver, nonces)

    ## Update our block hash and block num
    #if set_hash_and_height:
    #    set_latest_block_hash(block['hash'], driver=driver)
    #    set_latest_block_height(block['number'], driver=driver)
