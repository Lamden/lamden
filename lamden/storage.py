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
import threading

LATEST_BLOCK_HASH_KEY = '__latest_block.hash'
LATEST_BLOCK_HEIGHT_KEY = '__latest_block.height'
STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')
BLOCK_0 = {
    'number': 0,
    'hash': '0' * 64
}


class BlockStorage:
    def __init__(self, root=None, block_diver=None):
        self.current_thread = threading.current_thread()
        self.log = get_logger(f'[{self.current_thread.name}][BlockStorage]')
        self.root = pathlib.Path(root) if root is not None else STORAGE_HOME

        self.blocks_dir = self.root.joinpath('blocks')
        self.blocks_alias_dir = self.root.joinpath('block_alias')
        self.txs_dir = self.root.joinpath('txs')

        self.__build_directories()

        self.block_driver = block_diver or FSBlockDriver(root=self.blocks_dir)
        self.block_alias_driver = FSHashStorageDriver(root=self.blocks_alias_dir)
        self.tx_driver = FSHashStorageDriver(root=self.txs_dir)


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

    def __write_block(self, block: dict):
        hash_symlink_name = block.get('hash')

        filename = self.block_driver.write_block(block=block)
        file_path = self.block_driver.get_file_path(block_num=filename)
        self.block_alias_driver.write_symlink(
            hash_str=hash_symlink_name,
            link_to=file_path
        )

    def __write_tx(self, tx_hash, tx):
        self.tx_driver.write_file(hash_str=tx_hash, data=tx)

    def __fill_block(self, block):
        tx_hash = block.get('processed')
        tx = self.get_tx(tx_hash)
        block['processed'] = tx

    def block_exists(self, block_num: str) -> bool:
        return self.block_driver.block_exists(block_num=str(block_num))

    def is_genesis_block(self, block):
        return block.get('genesis', None) is not None

    def total_blocks(self):
        return self.block_driver.total_files

    def has_genesis(self):
        return self.block_driver.block_exists(block_num=0)

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
        encoded_block = encode(block)
        block = json.loads(encoded_block)

        if not self.is_genesis_block(block=block):

            tx, tx_hash = self.__cull_tx(block)

            if tx is None or tx_hash is None:
                raise ValueError('Block has no transaction information or malformed tx data.')

            self.__write_tx(tx_hash, tx)

        self.__write_block(block)

    def remove_block(self, v=None):
        if v is None:
            return None

        if isinstance(v, str) and hlc.is_hcl_timestamp(hlc_timestamp=v):
            nanos = hlc.nanos_from_hlc_timestamp(hlc_timestamp=v)
            if nanos > 0:
                v = str(nanos)

        block_num = str(v)
        block = self.block_driver.find_block(block_num=block_num)

        if block is None or self.is_genesis_block(block=block):
            return

        block_hash = block.get('hash')
        tx_hash = block.get('processed')

        self.block_driver.delete_block(block_num=block_num)
        self.block_alias_driver.remove_symlink(hash_str=block_hash)
        self.tx_driver.delete_file(hash_str=tx_hash)


    def get_block(self, v=None):
        if v is None:
            return None

        if isinstance(v, str) and hlc.is_hcl_timestamp(hlc_timestamp=v):
            nanos = hlc.nanos_from_hlc_timestamp(hlc_timestamp=v)
            if nanos > 0:
                v = str(nanos)

        try:
            int(v)
            block = self.block_driver.find_block(block_num=v)
        except ValueError:
            block = self.block_alias_driver.get_file(hash_str=v)

        if block is None:
            self.log.error(f'Block \'{v}\' was not found in storage.')
            return None

        if not self.is_genesis_block(block=block):
            self.__fill_block(block)

        return block

    def get_previous_block(self, v):
        if v is None:
            return None

        if hlc.is_hcl_timestamp(hlc_timestamp=v):
            v = hlc.nanos_from_hlc_timestamp(hlc_timestamp=v)
        else:
            if not isinstance(v, int) or v < 0:
                return None

        block = self.block_driver.find_previous_block(block_num=str(v))

        if block is None:
            return None

        if not self.is_genesis_block(block=block):
            self.__fill_block(block)

        return block

    def get_next_block(self, v):
        if v is None:
            return None

        if hlc.is_hcl_timestamp(hlc_timestamp=v):
            v = hlc.nanos_from_hlc_timestamp(hlc_timestamp=v)
        else:
            if not isinstance(v, int):
                return None

        block = self.block_driver.find_next_block(block_num=str(v))

        if not block:
            return None

        if not self.is_genesis_block(block=block):
            self.__fill_block(block)

        return block

    def get_latest_block(self):
        block = self.block_driver.find_previous_block(block_num='99999999999999999999')

        if not block:
            return None

        if not self.is_genesis_block(block=block):
            self.__fill_block(block)

        return block

    def get_tx(self, h):
        tx = self.tx_driver.get_file(hash_str=h)
        return tx

    def get_later_blocks(self, hlc_timestamp):
        later_blocks = []
        while True:
            if len(later_blocks) == 0:
                block_num = str(hlc.nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp))
            else:
                block_num = later_blocks[-1].get('number')

            block = self.block_driver.find_next_block(block_num=str(block_num))

            if block is None:
                break

            self.__fill_block(block=block)
            later_blocks.append(block)

        later_blocks = sorted(later_blocks, key=lambda x: x['number'])
        return later_blocks

    def set_previous_hash(self, block: dict):
        old_previous_hash = block.get('previous')
        previous_block = self.block_driver.find_previous_block(block_num=block.get('number'))

        new_previous_block_hash = previous_block.get('hash')
        block['previous'] = new_previous_block_hash

        if not self.block_alias_driver.is_symlink_valid(hash_str=old_previous_hash):
            self.block_alias_driver.remove_symlink(hash_str=old_previous_hash)


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

    def safe_set_nonce(self, sender, processor, value):
        current_nonce = self.get_nonce(sender=sender, processor=processor)

        if current_nonce is None:
            current_nonce = -1

        if value > current_nonce:
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
    # The BlockStorage class will handle encoding and decoding. Store and return blocks as JSON strings.

    def find_block(self, block_num: str) -> dict:
        # This method will take a block number and return that block and the next x amount of blocks
        raise NotImplementedError("Subclasses must implement this method.")

    def find_blocks(self, block_list: list) -> list:
        # This method will take a list of blocks and return the block content for each
        raise NotImplementedError("Subclasses must implement this method.")

    def write_block(self, block: dict) -> None:
        # Writes the content of a block dict to storage
        raise NotImplementedError("Subclasses must implement this method.")

    def write_blocks(self, block_list: list) -> None:
        # Writes a list of block dicts to storage
        raise NotImplementedError("Subclasses must implement this method.")

    def delete_block(self, block_num: str) -> None:
        # Deletes a block from storage
        raise NotImplementedError("Subclasses must implement this method.")

    def delete_blocks(self, block_list: list) -> None:
        # Deletes a list of block numbers from storage
        raise NotImplementedError("Subclasses must implement this method.")

    def find_previous_block(self, block_num: str) -> dict:
        # This method will take a block number and return the previous block
        raise NotImplementedError("Subclasses must implement this method.")

    def find_previous_blocks(self, block_num: str, amount_of_blocks: int) -> list:
        # This method will take a block number and return the previous x amount of blocks
        raise NotImplementedError("Subclasses must implement this method.")

    def find_next_block(self, block_num: str) -> dict:
        # This method will take a block number and return the next block
        raise NotImplementedError("Subclasses must implement this method.")

    def find_next_blocks(self, block_num: str, amount_of_blocks: int) -> list:
        # This method will take a block number and return the next x amount of blocks
        raise NotImplementedError("Subclasses must implement this method.")

    def block_exists(self, block_num: str) -> bool:
        # Checks if a block exists, returns Bool
        raise NotImplementedError("Subclasses must implement this method.")

    def get_total_blocks(self) -> int:
        # Returns the total current block count
        raise NotImplementedError("Subclasses must implement this method.")

class FSBlockDriver(BlockDriver):

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.total_files = 0
        self.initialized = False

        self.minute = 60_000_000_000
        self.hour = 3_600_000_000_000
        self.day = 86_400_000_000_000
        self.year = 31_536_000_000_000_000

        self._initialize()

    def _initialize(self):
        self.total_files = self.get_total_blocks()
        self.initialized = True

    def _find_directories(self, block_num: int) -> list:
        dir_levels = [self.year, self.day, self.hour, self.minute]
        directories = []
        for level in dir_levels:
            lower_bound = (block_num // level) * level
            upper_bound = lower_bound + level - 1
            dir_name = "{}_{}".format(lower_bound, upper_bound)
            directories.append(dir_name)
            block_num %= level
        return directories

    def _get_file_content(self, file_path: str) -> dict:
        try:
            with open(file_path) as file:
                return json.loads(file.read())
        except FileNotFoundError:
            return None

    def _iterate_files(self, path: str):
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_file():
                    yield entry
                elif entry.is_dir():
                    yield from self._iterate_files(entry.path)

    def _traverse_up(self, current_directory: str, direction: str) -> str:
        while True:
            parent_directory = os.path.dirname(current_directory)
            parent_directory_abs = os.path.abspath(parent_directory)
            try:
                subdirectories = sorted(os.listdir(parent_directory), key=lambda x: int(x.split('_')[0]))

                parent_directory_abs = os.path.abspath(parent_directory)

                current_directory_name = os.path.basename(current_directory)
                try:
                    index = subdirectories.index(current_directory_name)
                except Exception:
                    subdirectories.append(current_directory_name)
                    subdirectories = sorted(subdirectories, key=lambda x: int(x.split('_')[0]))
                    index = subdirectories.index(current_directory_name)

                if (direction == 'previous' and index > 0) or (direction == 'next' and index < len(subdirectories) - 1):
                    return os.path.join(parent_directory, subdirectories[index - 1 if direction == 'previous' else index + 1])

                if parent_directory_abs == self.root and ((direction == 'previous' and index == 0) or (direction == 'next' and index == len(subdirectories) - 1)):
                    return None
            except (FileNotFoundError, ValueError) as e:
                if parent_directory_abs == self.root:
                    return None

            current_directory = parent_directory

    def _traverse_down(self, directory: str, direction: str) -> dict:
        while os.path.isdir(directory):
            sub_items = sorted(os.listdir(directory), key=lambda x: int(x.split('_')[0]), reverse=(direction == 'previous'))
            directory = os.path.join(directory, sub_items[0])

            if os.path.isfile(directory):
                return self._get_file_content(file_path=directory)

        return None

    def _remove_empty_dirs(self, starting_dir: str):
        while pathlib.Path(starting_dir) != pathlib.Path(self.root):
            if not os.listdir(starting_dir):
                os.rmdir(starting_dir)
                starting_dir = os.path.dirname(starting_dir)
            else:
                break

    def get_file_path(self, block_num: str) -> str:
        input_number = int(block_num)
        current_dirs = self._find_directories(input_number)
        file_path = os.path.join(self.root, *current_dirs, block_num)
        return file_path

    def write_block(self, block: dict) -> str:
        block_num = str(block.get('number')).zfill(64)
        file_path = self.get_file_path(block_num)

        if not os.path.exists(file_path):
            self.total_files += 1

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w') as f:
            try:
                json.dump(block, f)
            except Exception as err:
                print(err)

        return block_num

    def write_blocks(self, block_list: list) -> None:
        for block in block_list:
            self.write_block(block=block)

    def move_block(self, src_file, block_num: str) -> None:
        src_path = str(src_file)
        dst_path = self.get_file_path(block_num)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.move(src_path, dst_path)

        return dst_path

    def delete_block(self, block_num: str) -> None:
        file_path = self.get_file_path(block_num.zfill(64))
        if os.path.exists(file_path):
            os.remove(file_path)

        self._remove_empty_dirs(starting_dir=os.path.dirname(file_path))

    def delete_blocks(self, block_list: list) -> None:
        for block_num in block_list:
            self.delete_block(block_num=block_num)

    def find_block(self, block_num: str) -> dict:
        path_to_file = self.get_file_path(block_num=str(block_num).zfill(64))
        block = self._get_file_content(file_path=path_to_file)
        return block

    def find_blocks(self, block_list: list) -> list:
        return [self.find_block(block_num=block_num) for block_num in block_list if self.find_block(block_num=block_num)]

    def find_next_block(self, block_num: str) -> dict:
        block_num_filled = str(block_num).zfill(64)
        block_path = self.get_file_path(block_num_filled)
        current_directory = os.path.dirname(block_path)

        if os.path.exists(current_directory):
            try:
                files = sorted(os.listdir(current_directory), key=lambda x: int(x.split('_')[0]))
            except FileNotFoundError:
                return None

            try:
                index = files.index(block_num_filled)
            except ValueError:
                files.append(block_num_filled)
                files.sort()
                index = files.index(block_num_filled)

            if index < len(files) - 1:
                return self._get_file_content(file_path=os.path.join(current_directory, files[index + 1]))

        next_directory = self._traverse_up(current_directory, 'next')
        if next_directory:
            return self._traverse_down(next_directory, 'next')

        return None

    def find_previous_block(self, block_num: str) -> dict:
        block_num_filled = str(block_num).zfill(64)
        block_path = self.get_file_path(block_num_filled)
        current_directory = os.path.dirname(block_path)

        if os.path.exists(current_directory):
            try:
                files = sorted(os.listdir(current_directory), key=lambda x: int(x.split('_')[0]))
            except FileNotFoundError:
                return None

            try:
                index = files.index(block_num_filled)
            except ValueError:
                files.append(block_num_filled)
                files.sort()
                index = files.index(block_num_filled)

            if index > 0:
                return self._get_file_content(file_path=os.path.join(current_directory, files[index - 1]))

        previous_directory = self._traverse_up(current_directory, 'previous')
        if previous_directory:
            return self._traverse_down(previous_directory, 'previous')

        return None

    def find_next_blocks(self, block_num: str, amount_of_blocks: int) -> list:
        blocks = [self.find_block(block_num=block_num)]
        for _ in range(amount_of_blocks):
            next_block = self.find_next_block(blocks[-1].get('number'))
            if next_block is None:
                break
            blocks.append(next_block)
        return blocks

    def find_previous_blocks(self, block_num: str, amount_of_blocks: int) -> list:
        blocks = [self.find_block(block_num=block_num)]
        for _ in range(amount_of_blocks):
            previous_block = self.find_previous_block(blocks[-1].get('number'))
            if previous_block is None:
                break
            blocks.append(previous_block)
        return blocks

    def get_total_blocks(self) -> int:
        count = 0
        for _ in self._iterate_files(self.root):
            count += 1
        return count

    def block_exists(self, block_num: str) -> bool:
        block_num_filled = str(block_num).zfill(64)
        block_file_path = self.get_file_path(block_num_filled)
        return os.path.exists(block_file_path)

class FSHashStorageDriver:
    def __init__(self, root: str):
        assert root is not None, "Must provide a root directory for storage"
        self.root_dir = root

    def get_directory(self, hash_str: str) -> str:
        return os.path.join(self.root_dir, hash_str[:2], hash_str[2:4], hash_str[4:6])

    def _remove_empty_dirs(self, starting_dir: str):
        while pathlib.Path(starting_dir) != pathlib.Path(self.root_dir):
            if not os.listdir(starting_dir):
                os.rmdir(starting_dir)
                starting_dir = os.path.dirname(starting_dir)
            else:
                break

    def write_file(self, hash_str: str, data: dict) -> None:
        dir_path = self.get_directory(hash_str)
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, hash_str)
        with open(file_path, "w") as f:
            json.dump(data, f)

    def delete_file(self, hash_str: str) -> None:
        dir_path = self.get_directory(hash_str=hash_str)
        file_path = os.path.join(dir_path, hash_str)
        if os.path.exists(file_path):
            os.remove(file_path)

        self._remove_empty_dirs(starting_dir=dir_path)

    def write_symlink(self, hash_str: str, link_to: str) -> None:
        dir_path = self.get_directory(hash_str)
        os.makedirs(dir_path, exist_ok=True)

        file_path = os.path.join(dir_path, hash_str)
        dest_path = os.path.abspath(link_to)

        if os.path.islink(file_path):
            os.unlink(file_path)

        os.symlink(dest_path, file_path)

    def remove_symlink(self, hash_str: str) -> None:
        dir_path = self.get_directory(hash_str)
        file_path = os.path.join(dir_path, hash_str)

        if os.path.islink(file_path):
            os.unlink(file_path)
            self._remove_empty_dirs(starting_dir=dir_path)

    def get_file(self, hash_str: str) -> dict:
        dir_path = self.get_directory(hash_str)
        file_path = os.path.join(dir_path, hash_str)

        if not os.path.exists(dir_path):
            return None

        if os.path.islink(file_path):
            file_path = os.readlink(file_path)

        with open(file_path, "r") as f:
            return json.loads(f.read())

    def is_symlink_valid(self, hash_str: str) -> bool:
        dir_path = self.get_directory(hash_str)
        file_path = os.path.join(dir_path, hash_str)

        if not os.path.islink(file_path):
            return False

        link_target = os.readlink(file_path)
        return os.path.exists(link_target)

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
