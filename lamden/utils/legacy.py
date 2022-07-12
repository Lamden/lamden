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

BLOCK_HASH_KEY = '_current_block_hash'
BLOCK_NUM_HEIGHT = '_current_block_height'
NONCE_KEY = '__n'
PENDING_NONCE_KEY = '__pn'

log = get_logger('STATE')


class DecimalEncoder(TypeEncoder):
    python_type = Decimal  # the Python type acted upon by this type codec

    def transform_python(self, value):
        d = Decimal(str(value))
        return Decimal128(d)


class ContractingDecimalEncoder(TypeEncoder):
    python_type = ContractingDecimal  # the Python type acted upon by this type codec

    def transform_python(self, value):
        d = Decimal(str(value._d))
        return Decimal128(d)


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
    def __init__(self, port=27027, db_name='lamden', nonce_collection='nonces', pending_collection='pending_nonces', config_path=lamden.__path__[0]):
        self.config_path = config_path

        self.port = port

        self.client = MongoClient()
        self.db = self.client.get_database(db_name)

        self.nonces = self.db.get_collection(nonce_collection, codec_options=codec_options)
        self.pending_nonces = self.db.get_collection(pending_collection, codec_options=codec_options)

    @staticmethod
    def get_one(sender, processor, db):
        v = db.find_one(
            {
                'sender': sender,
                'processor': processor
            }
        )

        if v is None:
            return None

        return v['value']

    @staticmethod
    def set_one(sender, processor, value, db):
        db.update_one(
            {
                'sender': sender,
                'processor': processor
            },
            {
                '$set':
                    {
                        'value': value
                    }
            }, upsert=True
        )

    def get_nonce(self, sender, processor):
        return self.get_one(sender, processor, self.nonces)

    def get_pending_nonce(self, sender, processor):
        return self.get_one(sender, processor, self.pending_nonces)

    def set_nonce(self, sender, processor, value):
        self.set_one(sender, processor, value, self.nonces)

    def set_pending_nonce(self, sender, processor, value):
        self.set_one(sender, processor, value, self.pending_nonces)

    def get_latest_nonce(self, sender, processor):
        latest_nonce = self.get_pending_nonce(sender=sender, processor=processor)

        if latest_nonce is None:
            latest_nonce = self.get_nonce(sender=sender, processor=processor)

        if latest_nonce is None:
            latest_nonce = 0

        return latest_nonce

    def flush(self):
        self.nonces.drop()
        self.pending_nonces.drop()

    def flush_pending(self):
        self.pending_nonces.drop()


def get_latest_block_hash(driver: ContractDriver):
    latest_hash = driver.get(BLOCK_HASH_KEY)
    if latest_hash is None:
        return '0' * 64
    return latest_hash


def set_latest_block_hash(h, driver: ContractDriver):
    driver.driver.set(BLOCK_HASH_KEY, h)


def get_latest_block_height(driver: ContractDriver):
    h = driver.get(BLOCK_NUM_HEIGHT)
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

    def __init__(self, port=27027, config_path=lamden.__path__[0], db='lamden', blocks_collection='blocks', tx_collection='tx'):
        # Setup configuration file to read constants
        self.config_path = config_path

        self.port = port

        self.client = MongoClient()
        self.db = self.client.get_database(db)

        self.blocks = self.db.get_collection(blocks_collection, codec_options=codec_options)
        self.txs = self.db.get_collection(tx_collection, codec_options=codec_options)

    def q(self, v):
        if isinstance(v, int):
            return {'number': v}
        return {'hash': v}

    def get_block(self, v=None, no_id=True):
        if v is None:
            return None

        q = self.q(v)
        block = self.blocks.find_one(q)

        if block is not None and no_id:
            block.pop('_id')

        return block

    def put(self, data, collection=BLOCK):
        if collection == BlockStorage.BLOCK:
            _id = self.blocks.insert_one(data)
            log.debug(data)
            del data['_id']
        elif collection == BlockStorage.TX:
            _id = self.txs.insert_one(data)
            del data['_id']
        else:
            return False

        return _id is not None

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
        tx = self.txs.find_one({'hash': h})

        if tx is not None and no_id:
            tx.pop('_id')

        return tx

    def drop_collections(self):
        self.blocks.drop()
        self.txs.drop()

    def flush(self):
        self.drop_collections()

    def store_block(self, block):
        if block.get('number') is not None:
            block['number'] = int(block['number'])

        self.put(block, BlockStorage.BLOCK)
        self.store_txs(block)

    def store_txs(self, block):
        if block.get('subblocks') is None:
            return

        for subblock in block['subblocks']:
            for tx in subblock['transactions']:
                self.put(tx, BlockStorage.TX)

    def delete_tx(self, h):
        self.txs.delete_one({'hash': h})

    def delete_block(self, v):
        block = self.get_block(v, no_id=False)

        if block is None:
            return

        for subblock in block['subblocks']:
            for tx in subblock['transactions']:
                self.delete_tx(tx['hash'])

        self.blocks.delete_one({'_id': block['_id']})
