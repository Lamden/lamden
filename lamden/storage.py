from contracting.db.driver import ContractDriver

from lamden.logger.base import get_logger
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db.driver import FSDriver
from contracting import config
from contracting.client import ContractingClient
from contracting.db.encoder import encode, decode, encode_kv
from lamden import contracts
from contracting.execution.executor import Executor

import pathlib

import json

import os

import shutil

## Block Format
'''
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

BLOCK_HASH_KEY = '_current_block_hash'
BLOCK_NUM_HEIGHT = '_current_block_height'
NONCE_KEY = '__n'
PENDING_NONCE_KEY = '__pn'
LAST_PROCESSED_HLC = '__last_processed_hlc'

STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')

log = get_logger('STATE')

BLOCK_0 = {
    'number': 0,
    'hash': '0' * 64
}


class StateManager:
    def __init__(self, metadata_root=STORAGE_HOME.joinpath('metadata'),
                 block_root=STORAGE_HOME,
                 nonce_collection=STORAGE_HOME.joinpath('nonces'),
                 pending_collection=STORAGE_HOME.joinpath('pending_nonces'),
                 genesis_path=contracts.__path__[0],
                 metering=False):

        self.metadata = MetaDataDriver(root=metadata_root)
        self.blocks = BlockStorage(home=block_root)
        self.nonces = NonceStorage(nonce_collection=nonce_collection, pending_collection=pending_collection)
        self.driver = ContractDriver()
        self.client = ContractingClient(
            driver=self.driver,
            submission_filename=genesis_path + '/submission.s.py'
        )
        self.executor = Executor(driver=self.driver, metering=metering)


class MetaDataDriver(FSDriver):
    PREPEND = '__metadata'

    def __init__(self, root=STORAGE_HOME.joinpath('metadata')):
        super().__init__(root)

    def build_key(self, k):
        return f'{MetaDataDriver.PREPEND}.{k}'

    def get_latest_block_hash(self):
        k = self.build_key(BLOCK_HASH_KEY)
        return self.get(k)

    def set_latest_block_hash(self, h):
        k = self.build_key(BLOCK_HASH_KEY)
        self.set(k, h)

    def get_latest_block_height(self):
        k = self.build_key(BLOCK_NUM_HEIGHT)
        h = self.get(k)
        if h is None:
            return 0

        if type(h) == ContractingDecimal:
            h = int(h._d)

        return h

    def set_latest_block_height(self, h):
        k = self.build_key(BLOCK_NUM_HEIGHT)
        self.set(k, h)

    def get_last_processed_hlc(self):
        k = self.build_key(LAST_PROCESSED_HLC)
        self.get(k)

    def set_last_processed_hlc(self, h):
        k = self.build_key(LAST_PROCESSED_HLC)
        self.set(k, h)


class BlockStorage:
    def __init__(self, home=STORAGE_HOME):
        if type(home) is str:
            home = pathlib.Path().joinpath(home)
        self.home = home

        self.blocks_dir = self.home.joinpath('blocks')
        self.blocks_alias_dir = self.blocks_dir.joinpath('alias')
        self.txs_dir = self.home.joinpath('txs')

        self.build_directories()

        self.cache = {}

    def build_directories(self):
        self.home.mkdir(exist_ok=True, parents=True)
        self.blocks_dir.mkdir(exist_ok=True, parents=True)
        self.blocks_alias_dir.mkdir(exist_ok=True, parents=True)
        self.txs_dir.mkdir(exist_ok=True, parents=True)

    def flush(self):
        try:
            shutil.rmtree(self.home)
            self.build_directories()
        except FileNotFoundError:
            pass

    def store_block_old(self, block):
        if block.get('subblocks') is None:
            return

        txs, hashes = self.cull_txs(block)
        self.write_block(block)
        self.write_txs(txs, hashes)

    def store_block(self, block):
        tx, tx_hash = self.cull_tx(block)

        if tx is None or tx_hash is None:
            raise ValueError('Block has no transaction information or malformed tx data.')

        self.write_block(block)
        self.write_txs([tx], [tx_hash])

    @staticmethod
    def cull_txs(block):
        # Pops all transactions from the block and replaces them with the hash only for storage space
        # Returns the data and hashes for storage in a different folder. Block is modified in place
        txs = []
        hashes = []
        for subblock in block['subblocks']:
            subblock_txs = []
            subblock_hashes = []

            for i in range(len(subblock['transactions'])):
                tx = subblock['transactions'].pop(0)

                subblock_txs.append(tx)
                subblock_hashes.append(tx['hash'])

            subblock['transactions'] = subblock_hashes
            try:
                subblock['subblock'] = int(subblock['subblock'])
            except:
                pass

            txs.extend(subblock_txs)
            hashes.extend(subblock_hashes)

        return txs, hashes

    @staticmethod
    def cull_tx(block):
        # Pops all transactions from the block and replaces them with the hash only for storage space
        # Returns the data and hashes for storage in a different folder. Block is modified in place
        try:
            tx = block.get('processed', None)
            tx_hash = tx.get('hash', None)
            block['processed'] = tx_hash

            return tx, tx_hash
        except Exception:
            return None, None

    def write_block(self, block):
        num = block.get('number')

        if type(num) == dict:
            num = num.get('__fixed__')
            block['number'] = num

        name = str(num).zfill(64)

        hash_symlink_name = block.get('hash')
        hlc_symlink_name = block.get('hlc_timestamp')

        encoded_block = encode(block)
        with open(self.blocks_dir.joinpath(name), 'w') as f:
            f.write(encoded_block)

        try:
            os.symlink(self.blocks_dir.joinpath(name), self.blocks_alias_dir.joinpath(hash_symlink_name))
            os.symlink(self.blocks_dir.joinpath(name), self.blocks_alias_dir.joinpath(hlc_symlink_name))
        except FileExistsError as err:
            print(err)
            pass

    def write_txs(self, txs, hashes):
        for file, data in zip(hashes, txs):
            with open(self.txs_dir.joinpath(file), 'w') as f:
                encoded_tx = encode(data)
                f.write(encoded_tx)

    def get_block_old(self, v=None, no_id=True):
        if v is None:
            return None

        try:
            if isinstance(v, int):
                f = open(self.blocks_dir.joinpath(str(v).zfill(64)))
            else:
                f = open(self.blocks_alias_dir.joinpath(v))
        except FileNotFoundError:
            return None

        encoded_block = f.read()

        block = decode(encoded_block)

        f.close()

        self.fill_block(block)

        return block

    def get_block(self, v=None):
        if v is None:
            return None

        try:
            if isinstance(v, int):
                f = open(self.blocks_dir.joinpath(str(v).zfill(64)))
            else:
                f = open(self.blocks_alias_dir.joinpath(v))
        except Exception as err:
            print(err)
            return None

        encoded_block = f.read()

        block = decode(encoded_block)

        f.close()

        self.fill_block(block)

        return block

    def get_previous_block(self, v=None):
        block = self.get_block(v=v)

        if block is None:
            return BLOCK_0

        return block

    def soft_store_block(self, hlc, block):
        self.cache[hlc] = block

    def commit(self, hlc):
        to_delete = []
        for _hlc, block in sorted(self.cache.items()):

            self.store_block(block)

            to_delete.append(_hlc)
            if _hlc == hlc:
                break

        for b in to_delete:
            self.cache.pop(b)

    def fill_block(self, block):
        tx_hash = block.get('processed')
        tx = self.get_tx(tx_hash)
        block['processed'] = tx

    def get_tx(self, h):
        try:
            f = open(self.txs_dir.joinpath(h))
            encoded_tx = f.read()

            tx = decode(encoded_tx)

            f.close()
        except FileNotFoundError:
            tx = None

        return tx

    def get_later_blocks(self, block_height, hlc_timestamp):
        blocks = []

        current_block = self.get_block(v=block_height)
        if current_block is None:
            return blocks

        current_block_hlc_timestamp = current_block.get('hlc_timestamp')

        if current_block_hlc_timestamp < hlc_timestamp:
            return blocks

        blocks.append(current_block)
        while hlc_timestamp < current_block_hlc_timestamp:
            block_height -= 1
            block = self.get_block(v=block_height)

            if block is None:
                break

            current_block_hlc_timestamp = block.get('hlc_timestamp', '')

            if hlc_timestamp < current_block_hlc_timestamp:
                blocks.insert(0, block)
            else:
                break

        return blocks


class NonceStorage:
    def __init__(self, nonce_collection=STORAGE_HOME.joinpath('nonces'),
                 pending_collection=STORAGE_HOME.joinpath('pending_nonces')):

        if type(nonce_collection) is str:
            nonce_collection = pathlib.Path().joinpath(nonce_collection)
        self.nonces = FSDriver(root=nonce_collection)

        if type(pending_collection) is str:
            pending_collection = pathlib.Path().joinpath(pending_collection)
        self.pending_nonces = FSDriver(root=pending_collection)

    @staticmethod
    def get_one(sender, processor, db: FSDriver):
        return db.get(f'{processor}{config.INDEX_SEPARATOR}{sender}')

    @staticmethod
    def set_one(sender, processor, value, db: FSDriver):
        return db.set(f'{processor}{config.INDEX_SEPARATOR}{sender}', value)

    # Move this to transaction.py
    def get_nonce(self, sender, processor):
        return self.get_one(sender, processor, self.nonces)

    # Move this to transaction.py
    def get_pending_nonce(self, sender, processor):
        return self.get_one(sender, processor, self.pending_nonces)

    def set_nonce(self, sender, processor, value):
        self.set_one(sender, processor, value, self.nonces)

    def set_pending_nonce(self, sender, processor, value):
        self.set_one(sender, processor, value, self.pending_nonces)

    # Move this to webserver.py
    def get_latest_nonce(self, sender, processor):
        latest_nonce = self.get_pending_nonce(sender=sender, processor=processor)

        if latest_nonce is None:
            latest_nonce = self.get_nonce(sender=sender, processor=processor)

        if latest_nonce is None:
            latest_nonce = 0

        return latest_nonce

    def flush(self):
        self.nonces.flush()
        self.pending_nonces.flush()

    def flush_pending(self):
        self.pending_nonces.flush()


def get_latest_block_hash(driver: ContractDriver):
    latest_hash = driver.get(BLOCK_HASH_KEY)
    if latest_hash is None:
        return '0' * 64
    return latest_hash


def set_latest_block_hash(h, driver: ContractDriver):
    driver.set(BLOCK_HASH_KEY, h)


def get_latest_block_height(driver: ContractDriver):
    h = driver.get(BLOCK_NUM_HEIGHT)
    if h is None:
        return 0

    if type(h) == ContractingDecimal:
        h = int(h._d)

    return h


def set_latest_block_height(h, driver: ContractDriver):
    #log.info(f'set_latest_block_height {h}')
    driver.set(BLOCK_NUM_HEIGHT, h)
    '''
    log.info('Driver')
    log.info(driver.driver)
    log.info('Cache')
    log.info(driver.cache)
    log.info('Writes')
    log.info(driver.pending_writes)
    log.info('Deltas')
    log.info(driver.pending_deltas)
    '''


def update_state_with_transaction(tx, driver: ContractDriver, nonces: NonceStorage):
    nonces_to_delete = []

    if tx['state'] is not None and len(tx['state']) > 0:
        for delta in tx['state']:
            driver.set(delta['key'], delta['value'])
            # log.debug(f"{delta['key']} -> {delta['value']}")

            nonces.set_nonce(
                sender=tx['transaction']['payload']['sender'],
                processor=tx['transaction']['payload']['processor'],
                value=tx['transaction']['payload']['nonce'] + 1
            )

            nonces_to_delete.append((tx['transaction']['payload']['sender'], tx['transaction']['payload']['processor']))

    for n in nonces_to_delete:
        nonces.set_pending_nonce(*n, value=None)


def update_state_with_block(block, driver: ContractDriver, nonces: NonceStorage, set_hash_and_height=True):
    if block.get('subblocks') is not None:
        for sb in block['subblocks']:
            for tx in sb['transactions']:
                update_state_with_transaction(tx, driver, nonces)

    # Update our block hash and block num
    if set_hash_and_height:
        set_latest_block_hash(block['hash'], driver=driver)
        set_latest_block_height(block['number'], driver=driver)

