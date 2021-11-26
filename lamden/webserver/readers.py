# Read-only drivers that are async for improved speed
from contracting.db.driver import ContractDriver
from pymongo import MongoClient, DESCENDING

import motor.motor_asyncio

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
    latest_hash = driver.get(BLOCK_HASH_KEY, mark=False)
    if latest_hash is None:
        return '0' * 64
    return latest_hash


def get_latest_block_height(driver: ContractDriver):
    h = driver.get(BLOCK_NUM_HEIGHT, mark=False)
    if h is None:
        return 0

    if type(h) == ContractingDecimal:
        h = int(h._d)

    return h


class AsyncBlockReader:
    BLOCK = 0
    TX = 1

    def __init__(self, port=27027, config_path=lamden.__path__[0], db='lamden', blocks_collection='blocks', tx_collection='tx'):
        # Setup configuration file to read constants
        self.config_path = config_path

        self.port = port

        self.client = motor.motor_asyncio.AsyncIOMotorClient()
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

    def get_last_n(self, n, collection=BLOCK):
        if collection == AsyncBlockReader.BLOCK:
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
