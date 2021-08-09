from contracting.db.driver import ContractDriver

from lamden.logger.base import get_logger
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db.driver import FSDriver

from contracting.db.encoder import encode, decode, encode_kv

import pathlib

import json

import os

import shutil

BLOCK_HASH_KEY = '_current_block_hash'
BLOCK_NUM_HEIGHT = '_current_block_height'
NONCE_KEY = '__n'
PENDING_NONCE_KEY = '__pn'

STORAGE_HOME = pathlib.Path().home().joinpath('.lamden')

log = get_logger('STATE')


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

    def store_block(self, block):
        if block.get('subblocks') is None:
            return

        txs, hashes = self.cull_txs(block)
        self.write_block(block)
        self.write_txs(txs, hashes)

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

    def write_block(self, block):
        num = block.get('number')

        if type(num) == dict:
            num = num.get('__fixed__')
            block['number'] = num

        name = str(num).zfill(64)

        symlink_name = block.get('hash')

        encoded_block = encode(block)
        with open(self.blocks_dir.joinpath(name), 'w') as f:
            f.write(encoded_block)

        try:
            os.symlink(self.blocks_dir.joinpath(name), self.blocks_alias_dir.joinpath(symlink_name))
        except FileExistsError:
            pass

    def write_txs(self, txs, hashes):
        for file, data in zip(hashes, txs):
            with open(self.txs_dir.joinpath(file), 'w') as f:
                encoded_tx = encode(data)
                f.write(encoded_tx)

    def get_block(self, v=None, no_id=True):
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
        for subblock in block['subblocks']:
            txs = []
            for i in range(len(subblock['transactions'])):
                tx = self.get_tx(subblock['transactions'][i])

                txs.append(tx)

            subblock['transactions'] = txs

    def get_tx(self, h):
        try:
            f = open(self.txs_dir.joinpath(h))
            encoded_tx = f.read()

            tx = decode(encoded_tx)

            f.close()
        except FileNotFoundError:
            tx = None

        return tx

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
        return db.get(f'{processor}/{sender}')

    @staticmethod
    def set_one(sender, processor, value, db: FSDriver):
        return db.set(f'{processor}/{sender}', value)

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

