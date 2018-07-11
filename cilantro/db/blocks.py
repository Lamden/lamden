from cilantro.logger import get_logger
import seneca.seneca_internal.storage.easy_db as t
from cilantro.db.tables import create_table
from cilantro.messages import BlockContender


log = get_logger("BlocksTable")

GENESIS_HASH = '0' * 64
GENESIS_EMPTY_STR = ''
GENESIS_TIMESTAMP = 0

# Block Data Fields
REQUIRED_COLS = {'merkle_root': str, 'merkle_leaves': str, 'prev_block_hash': str}
OPTIONAL_COLS = {'timestamp': int, 'masternode_signature': str}
ALL_COLS = {**REQUIRED_COLS, **OPTIONAL_COLS}

def build_blocks_table(ex, should_drop=True):
    blocks = t.Table('blocks', t.AutoIncrementColumn('number'), [t.Column('hash', t.str_len(64), True),] +
                     [t.Column(field_name, field_type) for field_name, field_type in ALL_COLS.items()])

    return create_table(ex, blocks, should_drop)


def seed_blocks(ex, blocks_table):
    blocks_table.insert([{
            'hash': GENESIS_HASH,
            'merkle_root': GENESIS_EMPTY_STR,
            'merkle_leaves': GENESIS_EMPTY_STR,
            'prev_block_hash': GENESIS_HASH,
            'timestamp': GENESIS_TIMESTAMP,
            'masternode_signature': GENESIS_EMPTY_STR,
        }]).run(ex)


class BlockStorageDriver:
    """
    This class provides a high level functional API for storing/retrieving blockchain data. It interfaces with the
    database under the hood using the process-specific DB Singleton. This allows all methods on this class to be
    implemented as static functions, since database cursors are provided via the Singleton instead of stored as
    properties on the BlockStorageDriver class.
    """

    @staticmethod
    def _validate_block_data(block_data: dict):
        """
        Validates that the dict block_data has keys for each block data column specified in ALL_COLS (at top of blocks.py)
        Raises an exception if a column is not specified.

        :param block_data: The dictionary of containing a key for each column in ALL_COLS
        (ie 'merkle_root', 'prev_block_hash', .. ect)
        :raises: An exception if the block data is invalid
        """
        pass

    @staticmethod
    def _compute_block_hash(block_data: dict) -> str:
        """
        Computes the block's hash as a function of the block data. The process for computing the block hash follows:
        - Binarize all block_data values
        - Lexicographically sort block_data keys
        - Concatenate binarized block_data values in this lexicographical order
        - SHA3 hash this concatenated binary

        :param block_data: The dictionary of containing a key for each column in ALL_COLS
        (ie 'merkle_root', 'prev_block_hash', .. ect)
        :return: The block's hash, as a 64 character hex string
        """
        pass

    @staticmethod
    def store_block(block_contender: BlockContender, merkle_leaves: list, merkle_root: str,
                    raw_transactions: list, publisher_sk: str, timestamp: int=0):
        """
        Persist a new block to the blockchain, along with the raw transactions associated with the block. An exception
        will be raised if an error occurs either validating the new block data, or storing the block.

        :param block_contender:
        :param merkle_leaves:
        :param merkle_root:
        :param raw_transactions:
        :param publisher_sk:
        :param timestamp:
        :return:
        """
        pass

    @staticmethod
    def retrieve_block_data(block_num: int=0, block_hash: str=''):
        pass

    @staticmethod
    def validate_blockchain(async=True):
        """
        Validates the cryptographic integrity of the block chain.
        :param async:
        """
        pass