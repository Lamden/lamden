from cilantro.logger import get_logger
import seneca.seneca_internal.storage.easy_db as t
from cilantro.db.tables import create_table
from cilantro.messages import BlockContender, TransactionBase
from cilantro.utils import is_valid_hex, Hasher
from cilantro.protocol.structures import MerkleTree
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.db import DB
from typing import List


log = get_logger("BlocksStorage")


# Block Data Fields
# REQUIRED_COLS must exist in all Cilantro based blockchains
REQUIRED_COLS = {'merkle_root': str, 'merkle_leaves': str, 'prev_block_hash': str, 'block_contender': str}  # TODO block_contender should be binary blob
# Custom Cilantro blockchains can configure OPTIONAL_COLS to add additional fields to block metadata
OPTIONAL_COLS = {'timestamp': int, 'masternode_signature': str, 'masternode_vk': str}

BLOCK_DATA_COLS = {**REQUIRED_COLS, **OPTIONAL_COLS}  # combines the 2 dictionaries


GENESIS_EMPTY_STR = ''
GENESIS_TIMESTAMP = 0
GENESIS_BLOCK_CONTENDER = ''
GENESIS_EMPTY_HASH = '0' * 64

GENESIS_BLOCK_DATA = {
    'merkle_root': GENESIS_EMPTY_STR,
    'merkle_leaves': GENESIS_EMPTY_STR,
    'prev_block_hash': GENESIS_EMPTY_HASH,
    'timestamp': GENESIS_TIMESTAMP,
    'masternode_signature': GENESIS_EMPTY_STR,
    'masternode_vk': GENESIS_EMPTY_STR,
    'block_contender': GENESIS_BLOCK_CONTENDER
}

"""
Below we have some horrible cringe worth functions to store block contenders are strings since EasyDB doesnt support 
binary types (yet)
TODO -- pls not this
"""
def _serialize_contender(block_contender: BlockContender) -> str:
    return block_contender.serialize().hex()
def _deserialize_contender(block_contender: str) -> BlockContender:
    return BlockContender.from_bytes(bytes.fromhex(block_contender))


def build_blocks_table(ex, should_drop=True):
    blocks = t.Table('blocks', t.AutoIncrementColumn('number'), [t.Column('hash', t.str_len(64), True),] +
                     [t.Column(field_name, field_type) for field_name, field_type in BLOCK_DATA_COLS.items()])

    return create_table(ex, blocks, should_drop)


def seed_blocks(ex, blocks_table):
    blocks_table.insert([{'hash': GENESIS_HASH, **GENESIS_BLOCK_DATA}]).run(ex)


class BlockStorageException(Exception): pass
class BlockStorageValidationException(BlockStorageException): pass

class InvalidBlockContenderException(BlockStorageValidationException): pass
class InvalidMerkleTreeException(BlockStorageValidationException): pass
class InvalidBlockSignatureException(BlockStorageValidationException): pass


class BlockStorageDriver:
    """
    This class provides a high level functional API for storing/retrieving blockchain data. It interfaces with the
    database under the hood using the process-specific DB Singleton. This allows all methods on this class to be
    implemented as static functions, since database cursors are provided via the Singleton instead of stored as
    properties on the BlockStorageDriver class.
    """

    @classmethod
    def store_block(cls, block_contender: BlockContender, raw_transactions: List[bytes], publisher_sk: str, timestamp: int = 0):
        """
        TODO -- think really hard and make sure that this is 'collision proof' (v unlikely, but still possible)

        Persist a new block to the blockchain, along with the raw transactions associated with the block. An exception
        will be raised if an error occurs either validating the new block data, or storing the block. Thus, it is
        recommended that this method is wrapped in a try block.

        :param block_contender:
        :param raw_transactions:
        :param publisher_sk:
        :param timestamp:
        :return: None
        :raises: An assertion error if invalid args are passed into this function, or a BlockStorageValidationException
         if validation fails on the attempted block
        """
        assert isinstance(block_contender, BlockContender), "Expected block_contender arg to be BlockContender instance"
        assert is_valid_hex(publisher_sk, 64), "Invalid signing key {}. Expected 64 char hex str".format(publisher_sk)

        # Build Merkle tree from raw_transactions
        tree = MerkleTree.from_raw_transactions(raw_transactions)

        prev_block_hash = cls._get_latest_block_hash()

        publisher_vk = ED25519Wallet.get_vk(publisher_sk)
        publisher_sig = ED25519Wallet.sign(publisher_sk, tree.root)

        # Build and validate block_data
        block_data = {
            'block_contender': block_contender,
            'timestamp': timestamp,
            'merkle_root': tree.root_as_hex,
            'merkle_leaves': tree.leaves_as_concat_hex_str,
            'prev_block_hash': prev_block_hash,
            'masternode_signature': publisher_sig,
            'masternode_vk': publisher_vk,
        }
        cls._validate_block_data(block_data)

        # Compute block hash
        block_hash = cls._compute_block_hash(block_data)

        # Convert block_contender to binary
        block_data['block_contender'] = _serialize_contender(block_data['block_contender'])

        # Finally, persist the data
        log.info("Attempting to persist new block with hash {}".format(block_hash))
        with DB() as db:
            res = db.tables.blocks.insert([{'hash': block_hash, **block_data}]).run(db.ex)
            log.debug("Result of persisting block query: {}".format(res))
            log.critical("Result of persisting block query: {}".format(res))

    @classmethod
    def retrieve_block(cls, block_num: int=0, block_hash: str='') -> dict:
        pass

    @classmethod
    def validate_blockchain(cls, async=True):
        """
        Validates the cryptographic integrity of the block chain.
        :param async:
        """
        pass

    @classmethod
    def _validate_block_data(cls, block_data: dict):
        """
        Validates the block_data dictionary. If any validation fails, an exception is raised.
        For a block_data dictionary to be valid, it must:
         - Have a key for each block data column specified in BLOCK_DATA_COLS (at top of blocks.py)
         - BlockContender successfully validates with the Merkle root (meaning all signatures in the BlockContender
           can be verified using the Merkle root as the message)
         - Merkle leaves contained in BlockContender (block_contender.nodes) match Merkle leaves in block_data dict
         - Merkle root is correct root if a Merkle tree is built from Merkle leaves
         - Masternode signature is valid (signature is valid using Merkle root as message and masternode_vk as vk)

        :param block_data: The dictionary containing a key for each column in BLOCK_DATA_COLS
        (ie 'merkle_root', 'prev_block_hash', .. ect)
        :raises: An BlockStorageValidationException (or subclass) if any validation fails
        """
        # Check block_data has all the necessary keys
        expected_keys = set(BLOCK_DATA_COLS.keys())
        actual_keys = set(block_data.keys())
        missing_keys = expected_keys - actual_keys
        extra_keys = actual_keys - expected_keys

        # Check for missing keys
        if len(missing_keys) > 0:
            raise BlockStorageValidationException("block_data keys {} missing key(s) {}".format(actual_keys, missing_keys))
        # Check for extra (unrecognized) keys
        if len(extra_keys) > 0:
            raise BlockStorageValidationException("block_data keys {} has unrecognized keys {}".format(actual_keys, extra_keys))

        # Validate Merkle Tree
        tree = MerkleTree.from_leaves_hex_str(block_data['merkle_leaves'])
        if tree.root_as_hex != block_data['merkle_root']:
            raise InvalidMerkleTreeException("Merkle Tree could not be validated for block_data {}".format(block_data))

        # Validate BlockContender nodes match merkle leaves
        block_leaves = block_data['block_contender'].merkle_leaves
        if len(block_leaves) != len(tree.leaves):
            raise InvalidBlockContenderException("Number of Merkle leaves on BlockContender {} does not match number of"
                                                 " leaves in MerkleTree {}".format(len(block_leaves), len(tree.leaves)))
        for block_leaf, merkle_leaf in zip(block_leaves, tree.leaves_as_hex):
            if block_leaf != merkle_leaf:
                raise InvalidBlockContenderException("BlockContender leaves do not match Merkle leaves\nblock leaves = "
                                                     "{}\nmerkle leaves = {}".format(block_leaves, tree.leaves_as_hex))

        # Validate MerkleSignatures inside BlockContender
        bc = block_data['block_contender']
        if not bc.validate_signatures():
            raise InvalidBlockContenderException("BlockContender signatures could not be validated! BC = {}".format(bc))

        # TODO validate MerkleSignatures are infact signed by valid delegates

        # Validate Masternode Signature
        if not ED25519Wallet.verify(block_data['masternode_vk'], bytes.fromhex(block_data['merkle_root']), block_data['masternode_signature']):
            raise InvalidBlockSignatureException("Could not validate Masternode's signature on block data")

    @classmethod
    def _compute_block_hash(cls, block_data: dict) -> str:
        """
        Computes the block's hash as a function of the block data. The process for computing the block hash follows:
        - Binarize all block_data values
        - Lexicographically sort block_data keys
        - Concatenate binarized block_data values in this lexicographical order
        - SHA3 hash this concatenated binary

        :param block_data: The dictionary of containing a key for each column in BLOCK_DATA_COLS
        (ie 'merkle_root', 'prev_block_hash', .. ect)
        :return: The block's hash, as a 64 character hex string
        """
        ordered_values = [block_data[key] for key in sorted(block_data.keys())]
        return Hasher.hash_iterable(ordered_values)

    @classmethod
    def _get_latest_block_hash(cls) -> str:
        """
        Looks into the DB, and returns the latest block's hash. If the latest block_hash is for whatever reason invalid,
        (ie. not valid 64 char hex string), then this method will raise an assertion.
        :return: A string, representing the latest (most recent) block's hash
        :raises: An assertion if the latest block hash is not vaild 64 character hex. If this happens, something was
        seriously messed up in the block storage process.
        """
        with DB() as db:
            row = db.tables.blocks.select().order_by('number', desc=True).limit(1).run(db.ex)[0]
            last_hash = row['hash']
            assert is_valid_hex(last_hash, length=64), "Latest block hash is invalid 64 char hex! Got {}".format(last_hash)

            return last_hash


# This needs to be declared below BlockStorageDriver class definition
# TODO put this in another file so its not just chillin down here
GENESIS_HASH = BlockStorageDriver._compute_block_hash(GENESIS_BLOCK_DATA)
