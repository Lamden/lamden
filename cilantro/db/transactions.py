from cilantro.logger import get_logger
import seneca.seneca_internal.storage.easy_db as t
from cilantro.db.tables import create_table


"""
Methods to create and seed the transactions table
"""


def build_transactions_table(ex, should_drop=True):
    transactions = t.Table('transactions',
                           t.Column('hash', t.str_len(64), True),
                           [
                               t.Column('data', str),
                               t.Column('block_hash', t.str_len(64)),  # TODO how to index this column?
                           ])
    return create_table(ex, transactions, should_drop)


def seed_transactions(ex, transactions_table):
    # Currently we are not seeding any transactions, but I provide this API for uniformity --davis
    pass


"""
Utility Functions to encode/decode block data for serialization 

TODO -- a lot of this encoding can be completely omitted or at least improved once we get blob types in EasyDB
"""


def encode_tx(raw_transaction: bytes) -> str:
    hex_str = raw_transaction.hex()
    return hex_str


def decode_tx(encoded_tx: str) -> bytes:
    return bytes.fromhex(encoded_tx)
