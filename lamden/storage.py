from contracting.db.driver import ContractDriver
from pymongo import MongoClient, DESCENDING

from bson.decimal128 import Decimal128
from bson.codec_options import TypeCodec, TypeEncoder, TypeDecoder
from bson.codec_options import TypeRegistry
from bson.codec_options import CodecOptions

from decimal import Decimal

import lamden
from lamden.logger.base import get_logger
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db.driver import FSDriver

BLOCK_HASH_KEY = '_current_block_hash'
BLOCK_NUM_HEIGHT = '_current_block_height'
NONCE_KEY = '__n'
PENDING_NONCE_KEY = '__pn'

log = get_logger('STATE')


class DecimalEncoder(TypeEncoder):
    python_type = Decimal  # the Python type acted upon by this type codec

    def transform_python(self, value):
        return Decimal128(value)


class ContractingDecimalEncoder(TypeEncoder):
    python_type = ContractingDecimal  # the Python type acted upon by this type codec

    def transform_python(self, value):
        return Decimal128(value._d)


class DecimalDecoder(TypeDecoder):
    bson_type = Decimal128

    def transform_bson(self, value):
        return value.to_decimal()

# class ContractingDecimalCodec(TypeCodec):
#     python_type = ContractingDecimal  # the Python type acted upon by this type codec
#     bson_type = Decimal128  # the BSON type acted upon by this type codec
#
#     def transform_python(self, value):
#         return Decimal128(value._d)
#
#     def transform_bson(self, value):
#         return value.to_decimal()


type_registry = TypeRegistry([DecimalDecoder(), DecimalEncoder(), ContractingDecimalEncoder()])
codec_options = CodecOptions(type_registry=type_registry)


class NonceStorage:
    def __init__(self, nonce_collection='~/lamden/nonces', pending_collection='~/lamden/pending_nonces'):
        self.nonces = FSDriver(root=nonce_collection)
        self.pending_nonces = FSDriver(root=pending_collection)

    @staticmethod
    def get_one(sender, processor, db: FSDriver):
        return db.get(f'{sender}/{processor}')

    @staticmethod
    def set_one(sender, processor, value, db: FSDriver):
        return db.set(f'{sender}/{processor}', value)

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
    latest_hash = driver.get(BLOCK_HASH_KEY, mark=False)
    if latest_hash is None:
        return '0' * 64
    return latest_hash


def set_latest_block_hash(h, driver: ContractDriver):
    driver.driver.set(BLOCK_HASH_KEY, h)


def get_latest_block_height(driver: ContractDriver):
    h = driver.get(BLOCK_NUM_HEIGHT, mark=False)
    if h is None:
        return 0

    if type(h) == ContractingDecimal:
        h = int(h._d)

    return h


def set_latest_block_height(h, driver: ContractDriver):
    driver.driver.set(BLOCK_NUM_HEIGHT, h)


def update_state_with_transaction(tx, driver: ContractDriver, nonces: NonceStorage):
    nonces_to_delete = []

    if tx['state'] is not None and len(tx['state']) > 0:
        for delta in tx['state']:
            driver.driver.set(delta['key'], delta['value'])
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


class BlockStorage:
    BLOCK = 0
    TX = 1

    def __init__(self, blocks_collection='~/lamden/blocks', tx_collection='~/lamden/tx'):
        # Setup configuration file to read constants
        self.blocks = FSDriver(blocks_collection)
        self.txs = FSDriver(tx_collection)

    def q(self, v):
        if isinstance(v, int):
            return str(v).zfill(32)
        return v

    def get_block(self, v=None, no_id=True):
        if v is None:
            return None

        q = self.q(v)
        block = self.blocks.get(q)

        return block

    def put(self, data, collection=BLOCK):
        if collection == BlockStorage.BLOCK:
            name = str(data['number']).zfill(32)

            self.blocks.set(name, data)

            # Change to symbolic link
            self.blocks.set(data['hash'], data)

        elif collection == BlockStorage.TX:
            self.txs.set(data['hash'], data)
        else:
            return False

        return True

    def get_last_n(self, n, collection=BLOCK):
        if collection == BlockStorage.BLOCK:
            c = self.blocks
        else:
            return None

        block_query = c.find({}, {'_id': False}).sort(
            'number', DESCENDING
        ).limit(n)

        blocks = [block for block in block_query]

        if len(blocks) > 1:
            first_block_num = blocks[0].get('number')
            last_block_num = blocks[-1].get('number')

            assert first_block_num > last_block_num, "Blocks are not descending."

        return blocks

    def get_tx(self, h, no_id=True):
        return self.txs.get(h)

    def drop_collections(self):
        self.blocks.flush()
        self.txs.flush()

    def flush(self):
        self.drop_collections()

    def store_block(self, block):
        self.put(block, BlockStorage.BLOCK)
        self.store_txs(block)

    def store_txs(self, block):
        if block.get('subblocks') is None:
            return

        for subblock in block['subblocks']:
            for tx in subblock['transactions']:
                self.put(tx, BlockStorage.TX)
