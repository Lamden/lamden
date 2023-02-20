from contracting import config
from contracting.db.driver import ContractDriver, FSDriver
from contracting.db.encoder import encode, decode
from contracting.stdlib.bridge.decimal import ContractingDecimal
from lamden.logger.base import get_logger
from lamden.utils import hlc
import os
import pathlib
import shutil

# NOTE: move state related stuff out of here. see TODO's below.

'''                             Block Format

{
    "hash": "hashed(hlc_timestamp + number + previous_hash)",
    "number": number,
    "hlc_timestamp": "some hlc_timestamp",
    "previous": "0000000000000000000000000000000000000000000000000000000000000000",
    "proofs": [
        {
            'signature': "node_1_sig",
            'signer': "node_1_vk"
        },
        {
            'signature': "node_5_sig",
            'signer': "node_5_vk"
        },
        {
            'signature': "node_25_sig",
            'signer': "node_25_vk"
        }
    ],
    'processed': {
        "hash": "467ebaa7304d6bc9871ba0ef530e5e8b6dd7331f6c3ae7a58fa3e482c77275f3",
        "hlc_timestamp": hlc_timestamp,
        "result": "None",
        "stamps_used": 18,
        "state": [
              {
                "key": "lets",
                "value": "go"
              },
              {
                "key": "blue",
                "value": "jays"
              }
        ],
        "status": 0,
        "transaction": {
            "metadata":{
                "signature": "some sig"
            },
            "payload" : { LAMDEN PAYLOAD OBJ }
        }
      }
  }        
'''

LATEST_BLOCK_HASH_KEY = '__latest_block.hash'
LATEST_BLOCK_HEIGHT_KEY = '__latest_block.height'
STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')
BLOCK_0 = {
    'number': 0,
    'hash': '0' * 64
}

class BlockStorage:
    def __init__(self, root=None):
        self.log = get_logger('BlockStorage')
        self.root = pathlib.Path(root) if root is not None else STORAGE_HOME
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
