from cilantro.logger import get_logger
import seneca.seneca_internal.storage.easy_db as t
from cilantro.db.tables import create_table


log = get_logger("BlocksTable")

GENESIS_HASH = '0' * 64
GENESIS_TREE = ''
GENESIS_SIGS = ''


def build_blocks_table(ex, should_drop=True):
    blocks = t.Table('blocks',
                     t.AutoIncrementColumn('number'),
                     [
                         t.Column('hash', t.str_len(64), True),
                         t.Column('tree', str),
                         t.Column('signatures', str),
                     ])

    return create_table(ex, blocks, should_drop)


def seed_blocks(ex, blocks_table):
    blocks_table.insert([{
            'hash': GENESIS_HASH,
            'tree': GENESIS_TREE,
            'signatures': GENESIS_SIGS,
        }]).run(ex)

def validate_blockchain(ex, blocks_table):
    """
    Validates the cryptographic integrity of the block chain. This involves:

    :param ex:
    :param blocks_table:
    :return: None
    :raises: An exception/assertion if
    """
    pass
