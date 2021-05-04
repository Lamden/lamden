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
        return Decimal128(value)


class ContractingDecimalEncoder(TypeEncoder):
    python_type = ContractingDecimal  # the Python type acted upon by this type codec

    def transform_python(self, value):
        return Decimal128(value._d)


class DecimalDecoder(TypeDecoder):
    bson_type = Decimal128

    def transform_bson(self, value):
        return value.to_decimal()


type_registry = TypeRegistry([DecimalDecoder(), DecimalEncoder(), ContractingDecimalEncoder()])
codec_options = CodecOptions(type_registry=type_registry)


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


class LegacyBlockStorage:
    def __init__(self, port=27027, config_path=lamden.__path__[0], db='lamden', blocks_collection='blocks'):
        # Setup configuration file to read constants
        self.config_path = config_path

        self.port = port

        self.client = MongoClient()
        self.db = self.client.get_database(db)

        self.blocks = self.db.get_collection(blocks_collection, codec_options=codec_options)

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
