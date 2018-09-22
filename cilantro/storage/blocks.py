from cilantro.logger import get_logger
import seneca.engine.storage.easy_db as t
from seneca.engine.storage.easy_db import and_, or_
from cilantro.storage.tables import create_table
from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.utils import is_valid_hex, Hasher
from cilantro.protocol.structures import MerkleTree
from cilantro.protocol import wallet
from cilantro.storage.db import DB
from cilantro.storage.transactions import encode_tx, decode_tx
from typing import List
import time

from cilantro.messages.block_data.block_metadata import BlockMetaData, NewBlockNotification
# import cilantro.messages.block_data.block_metadata.BlockMetaData

log = get_logger("BlocksStorage")

"""
Block Data fields


REQUIRED_COLS must exist in all Cilantro based blockchains
Custom Cilantro configurations can configure OPTIONAL_COLS to add additional fields to block metadata
"""
REQUIRED_COLS = {'merkle_root': str, 'merkle_leaves': str, 'prev_block_hash': str, 'block_contender': str}  # TODO block_contender should be binary blob
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
Methods to create and seed the 'blocks' table
"""


def build_blocks_table(ex, should_drop=True):
    blocks = t.Table('blocks', t.AutoIncrementColumn('number'), [t.Column('hash', t.str_len(64), True)] +
                     [t.Column(field_name, field_type) for field_name, field_type in BLOCK_DATA_COLS.items()])

    return create_table(ex, blocks, should_drop)


def seed_blocks(ex, blocks_table):
    blocks_table.insert([{'hash': GENESIS_HASH, **GENESIS_BLOCK_DATA}]).run(ex)


"""
Utility Functions to encode/decode block data for serialization

TODO -- a lot of this encoding can be completely omitted or at least improved once we get blob types in EasyDB
"""


def _serialize_contender(block_contender: BlockContender) -> str:
    hex_str = block_contender.serialize().hex()
    return hex_str


def _deserialize_contender(block_contender: str) -> BlockContender:
    # Genesis Block Contender is None/Empty and thus should not be deserialized
    if block_contender == GENESIS_BLOCK_CONTENDER:
        return block_contender
    return BlockContender.from_bytes(bytes.fromhex(block_contender))


"""
Custom Exceptions for block storage operations
"""
class BlockStorageException(Exception): pass
class BlockStorageValidationException(BlockStorageException): pass
class BlockStorageDatabaseException(BlockStorageException): pass

class InvalidBlockContenderException(BlockStorageValidationException): pass
class InvalidMerkleTreeException(BlockStorageValidationException): pass
class InvalidBlockSignatureException(BlockStorageValidationException): pass
class InvalidBlockHashException(BlockStorageValidationException): pass
class InvalidBlockLinkException(BlockStorageValidationException): pass

class BlockStorageDriver:
    """
    This class provides a high level functional API for storing/retrieving blockchain data. It interfaces with the
    database under the hood using the process-specific DB Singleton. This allows all methods on this class to be
    implemented as class methods, since database cursors are provided via the Singleton instead of stored as
    properties on the BlockStorageDriver class/instance.
    """

    def __init__(self):
        raise NotImplementedError("Do not instantiate this class! Instead, use the class methods.")

    @classmethod
    def store_pre_validated_block(cls, block_contender: BlockContender, raw_transactions: List[bytes], publisher_sk: str,
                    timestamp: int = 0) -> str:
        assert isinstance(block_contender, BlockContender), "Expected block_contender arg to be BlockContender instance"
        assert is_valid_hex(publisher_sk, 64), "Invalid signing key {}. Expected 64 char hex str".format(publisher_sk)



        if not timestamp:
            timestamp = int(time.time())

        tree = MerkleTree.from_raw_transactions(raw_transactions)

        publisher_vk = wallet.get_vk(publisher_sk)
        publisher_sig = wallet.sign(publisher_sk, tree.root)

        # Build and validate block_data
        block_data = {
            'block_contender': block_contender,
            'timestamp': timestamp,
            'merkle_root': tree.root_as_hex,
            'merkle_leaves': tree.leaves_as_concat_hex_str,
            'prev_block_hash': cls.get_latest_block_hash(),
            'masternode_signature': publisher_sig,
            'masternode_vk': publisher_vk,
        }

        # NOTE: Each sub-block must already be validated during aggregation

        # Compute block hash
        block_hash = cls.compute_block_hash(block_data)

        # Encode block data for serialization
        log.info("Attempting to persist new block with hash {}".format(block_hash))
        block_data = cls._encode_block(block_data)

        # Finally, persist the data

        with DB() as db:
            # Store block
            res = db.tables.blocks.insert([{'hash': block_hash, **block_data}]).run(db.ex)
            if res:
                log.success2("Successfully inserted new block with number {} and hash {}".format(res['last_row_id'], block_hash))
            else:
                raise BlockStorageDatabaseException("Error inserting block! Got None/False result back "
                                                    "from insert query. Result={}".format(res))

            # Store raw transactions
            log.info("Attempting to store {} raw transactions associated with block hash {}"
                     .format(len(raw_transactions), block_hash))
            tx_rows = [{'hash': Hasher.hash(raw_tx), 'data': encode_tx(raw_tx), 'block_hash': block_hash}
                       for raw_tx in raw_transactions]

            res = db.tables.transactions.insert(tx_rows).run(db.ex)
            if res:
                log.info("Successfully inserted {} transactions".format(res['row_count']))
            else:
                log.error("Error inserting raw transactions! Got None from insert query. Result={}".format(res))

            return block_hash, publisher_sig

    @classmethod
    def store_block(cls, block_contender: BlockContender, raw_transactions: List[bytes], publisher_sk: str,
                    timestamp: int = 0) -> str:
        """
        Persist a new block to the blockchain, along with the raw transactions associated with the block. An exception
        will be raised if an error occurs either validating the new block data, or storing the block. Thus, it is
        recommended that this method is wrapped in a try block. If the block was successfully stored, this method will
        return the hash of the stored block.

        :param block_contender: A BlockContender instance
        :param raw_transactions: A list of ordered raw transactions contained in the block
        :param publisher_sk: The signing key of the publisher (a Masternode) who is publishing the block
        :param timestamp: The time the block was published, in unix epoch time. If 0, time.time() is used
        :return: The hash of the stored block
        :raises: An assertion error if invalid args are passed into this function, or a BlockStorageValidationException
         if validation fails on the attempted block

        TODO -- think really hard and make sure that this is 'collision proof' (extremely unlikely, but still possible)
        - could there be a hash collision in the Merkle tree nodes?
        - hash collision in block hash space?
        - hash collision in transaction space?
        """
        assert isinstance(block_contender, BlockContender), "Expected block_contender arg to be BlockContender instance"
        assert is_valid_hex(publisher_sk, 64), "Invalid signing key {}. Expected 64 char hex str".format(publisher_sk)

        if not timestamp:
            timestamp = int(time.time())

        tree = MerkleTree.from_raw_transactions(raw_transactions)

        publisher_vk = wallet.get_vk(publisher_sk)
        publisher_sig = wallet.sign(publisher_sk, tree.root)

        # Build and validate block_data
        block_data = {
            'block_contender': block_contender,
            'timestamp': timestamp,
            'merkle_root': tree.root_as_hex,
            'merkle_leaves': tree.leaves_as_concat_hex_str,
            'prev_block_hash': cls.get_latest_block_hash(),
            'masternode_signature': publisher_sig,
            'masternode_vk': publisher_vk,
        }
        cls.validate_block_data(block_data)

        # Compute block hash
        block_hash = cls.compute_block_hash(block_data)

        # Encode block data for serialization
        log.info("Attempting to persist new block with hash {}".format(block_hash))
        block_data = cls._encode_block(block_data)

        # Finally, persist the data
        with DB() as db:
            # Store block
            res = db.tables.blocks.insert([{'hash': block_hash, **block_data}]).run(db.ex)
            if res:
                log.success2("Successfully inserted new block with number {} and hash {}".format(res['last_row_id'], block_hash))
            else:
                raise BlockStorageDatabaseException("Error inserting block! Got None/False result back "
                                                    "from insert query. Result={}".format(res))

            # Store raw transactions
            log.info("Attempting to store {} raw transactions associated with block hash {}"
                     .format(len(raw_transactions), block_hash))
            tx_rows = [{'hash': Hasher.hash(raw_tx), 'data': encode_tx(raw_tx), 'block_hash': block_hash}
                       for raw_tx in raw_transactions]

            res = db.tables.transactions.insert(tx_rows).run(db.ex)
            if res:
                log.info("Successfully inserted {} transactions".format(res['row_count']))
            else:
                log.error("Error inserting raw transactions! Got None from insert query. Result={}".format(res))

            return block_hash

    @classmethod
    def store_block_from_meta(cls, block: BlockMetaData or NewBlockNotification) -> str:
        """
        Stores a block from a BlockMetaData object. This block must be the child of the current lastest block.
        :param block: The BlockMetaData object containing all of the block's data (excluding the raw transactions)
        :return: The hash of the stored block (as a string)
        :raises: A BlockStorageException (or specific subclass) if any validation or storage fails
        """
        assert issubclass(type(block), BlockMetaData), "Can only store BlockMetaData objects or subclasses"

        # Ensure this block's previous hash matches the latest block hash in the DB
        if block.prev_block_hash != cls.get_latest_block_hash():
            raise InvalidBlockLinkException("Attempted to store a block with previous_hash {} that does not match the "
                                            "database latest block hash {}".format(block.prev_block_hash,
                                                                                   cls.get_latest_block_hash()))

        with DB() as db:
            encoded_block_data = cls._encode_block(block.block_dict())
            res = db.tables.blocks.insert([encoded_block_data]).run(db.ex)
            if res:
                log.success2("Successfully inserted new block with number {} and hash {}".format(res['last_row_id'], block.block_hash))
            else:
                raise BlockStorageDatabaseException("Error inserting block! Got None/False result back "
                                                    "from insert query. Result={}".format(res))

            return block.block_hash


    @classmethod
    def get_block(cls, number: int=0, hash: str='', include_number=True) -> dict or None:
        """
        Retrieves a block by its hash, or autoincrement number. Returns a dictionary with a key for each column in the
        blocks table. Returns None if no block with the specified hash/number is found.
        :param number: The number of the block to fetch. The genesis block is number 1, and the first 'real' block
        is number 2, and so on.
        :param hash: The hash of the block to lookup. Must be valid 64 char hex string
        :return: A dictionary, containing a key for each column in the blocks table.
        """
        assert bool(number > 0) ^ bool(hash), "Either 'number' XOR 'hash' arg must be given"

        with DB() as db:
            blocks = db.tables.blocks

            if number > 0:
                block = blocks.select().where(blocks.number == number).run(db.ex)
                return cls._decode_block(block[0]) if block else None

            elif hash:
                assert is_valid_hex(hash, length=64), "Invalid block hash {}".format(hash)
                block = blocks.select().where(blocks.hash == hash).run(db.ex)

                if block:
                    b = cls._decode_block(block[0])
                    if not include_number:
                        del b['number']
                    return b
                else:
                    return None

    @classmethod
    def get_latest_block(cls, include_number=True) -> dict:
        """
        Retrieves the latest block published in the chain.
        :return: A dictionary representing the latest block, containing a key for each column in the blocks table.
        """
        with DB() as db:
            latest = db.tables.blocks.select().order_by('number', desc=True).limit(1).run(db.ex)
            assert latest, "No blocks found! There should be a genesis. Was the database properly seeded?"

            # TODO unit tests around include_number functionality
            block = cls._decode_block(latest[0])
            if not include_number:
                del block['number']
            return block

    @classmethod
    def get_child_block_hashes(cls, parent_hash: str, limit=0) -> List[str] or None:
        """
        Retrieve a list of child block hashes from a given a parent block. In other words, this method gets the hashes
        for all blocks created "after" the specified block with hash 'parent_hash'.
        :param parent_hash: The hash of the parent block
        :param limit: If specified,
        :return: A list of hashes for the blocks that descend the parent block. These will be sorted by their order
        in the block chain, such that the first element is the block immediately after parent_hash, and the last element
        is the latest block in the block chain. Returns None if parent_hash is already the latest block, or if no
        block with 'parent_hash' can be found.
        """
        assert is_valid_hex(parent_hash, 64), "parent_hash {} is not valid 64 char hex str".format(parent_hash)
        assert limit >= 0, "Limit must be >= 0 (not {})".format(limit)

        # TODO implement functionality for limits
        if limit:
            raise NotImplementedError("Limiting logic not implemented")

        # TODO optimize this once we get more functionality in EasyDB ...
        # we would like to select all rows where the number >= the number associated with 'parent_hash', ordered
        # ascending by number. For now, we must do this in 2 queries
        with DB() as db:
            blocks = db.tables.blocks

            # Get block index number associated with 'parent_hash'
            row = blocks.select().where(blocks.hash == parent_hash).run(db.ex)
            if not row:
                log.warning("No block with hash {} could be found!".format(parent_hash))
                return None
            parent_number = row[0]['number']

            rows = blocks.select('hash').where(blocks.number > parent_number).order_by('number', desc=False).run(db.ex)
            if not rows:
                return None
            return [row['hash'] for row in rows]

    @classmethod
    def get_latest_block_hash(cls) -> str:
        """
        Looks into the DB, and returns the latest block's hash. If the latest block_hash is for whatever reason invalid,
        (ie. not valid 64 char hex string), then this method will raise an assertion.
        :return: A string, representing the latest (most recent) block's hash
        :raises: An assertion if the latest block hash is not vaild 64 character hex. If this happens, something was
        seriously messed up in the block storage process.

        # TODO this can perhaps be made more efficient by memoizing the new block_hash each time we store it
        """
        with DB() as db:
            row = db.tables.blocks.select('hash').order_by('number', desc=True).limit(1).run(db.ex)[0]
            last_hash = row['hash']

            assert is_valid_hex(last_hash, length=64), "Latest block hash is invalid 64 char hex! Got {}".format(last_hash)

            return last_hash

    @classmethod
    def get_raw_transactions(cls, tx_hashes: str or list) -> bytes or None:
        """
        Retrieves a single raw transaction from its hash. Returns None if no transaction for that hash can be found
        :param tx_hashes: The hash of the raw transaction to lookup (as a str), or a list of hashes. Hashes should
        be 64 character hex strings.
        :return: The raw transactions as bytes, or None if no transaction with that hash can be found
        """
        return cls._get_raw_transactions(hashes=tx_hashes, is_block_hashes=False)

    @classmethod
    def get_raw_transactions_from_block(cls, block_hashes: str or list) -> List[bytes] or None:
        """
        Retrieves a list of raw transactions associated with a particular block. Returns None if no block with
        the given hash can be found.
        :param block_hashes: A single transaction hash (as a 64 char string), or a list of transaction hashes
        :return: A list of raw transactions each as bytes, or None if no block with the given hash can be found
        """
        return cls._get_raw_transactions(hashes=block_hashes, is_block_hashes=True)

    @classmethod
    def validate_blockchain(cls, async=False):
        """
        Validates the cryptographic integrity of the blockchain. See spec in docs folder for details on what defines a
        valid blockchain structure.
        # TODO docstring
        :param async: If true, run this in a separate process
        :raises: An exception if validation fails
        """
        start = time.time()

        if async:
            raise NotImplementedError()

        with DB() as db:
            blocks = db.tables.blocks.select().order_by('number', desc=False).run(db.ex)
            assert blocks, "No blocks found! There should be a genesis. Was the database properly seeded?"

            for i in range(len(blocks) - 1):
                cls._validate_block_link(cls._decode_block(blocks[i]), cls._decode_block(blocks[i+1]))

        log.info("Blockchain validation completed successfully in {} seconds.".format(round(time.time() - start, 2)))

    @classmethod
    def validate_block_data(cls, block_data: dict):
        """
        Validates the block_data dictionary. 'block_data' should be a strict subset of the 'block' dictionary, keys for all
        columns in the block table EXCEPT 'number' and 'hash'. If any validation fails, an exception is raised.
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

        # Validate MerkleSignatures inside BlockContender match Merkle leaves from raw transactions
        bc = block_data['block_contender']
        if not bc.validate_signatures():
            raise InvalidBlockContenderException("BlockContender signatures could not be validated! BC = {}".format(bc))

        # TODO validate MerkleSignatures are infact signed by valid TESTNET_DELEGATES
        # this is tricky b/c we would need to know who the TESTNET_DELEGATES were at the time of the block, not necessarily the
        # current TESTNET_DELEGATES

        # Validate Masternode Signature
        if not is_valid_hex(block_data['masternode_vk'], length=64):
            raise InvalidBlockSignatureException("Invalid verifying key for field masternode_vk: {}"
                                                 .format(block_data['masternode_vk']))
        if not wallet.verify(block_data['masternode_vk'], bytes.fromhex(block_data['merkle_root']), block_data['masternode_signature']):
            raise InvalidBlockSignatureException("Could not validate Masternode's signature on block data")

        # TODO validate this is signed by a real Masternode. This is tricky for reasons mentioned above

    @classmethod
    def compute_block_hash(cls, block_data: dict) -> str:
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
    def _get_raw_transactions(cls, hashes: str or list, is_block_hashes=False):
        """
        Helper method to query raw transactions, either from a list of hashes or a single hash. If is_block_hashes=True,
        then the hashes are assumed to refer to block hashes, in which case all the transactions belonging to that
        particular block is returned.
        :param hashes: A single hash (as a string), or a list of hashes
        :param is_block_hashes: If true, 'hashes' is assumed to refer to block hashes, and all transactions belonging
        to the specified block hash(es) will be returned. If False, 'hashes' are assumed to be transaction hashes.
        :return: A list of raw transactions, each as bytes, or None if no block with the given hash can be found
        """
        assert isinstance(hashes, str) or isinstance(hashes, list), "Expected hashes to be a str or list"

        if isinstance(hashes, str):
            hashes = [hashes]

        for h in hashes:
            assert is_valid_hex(h, length=64), "Expected hashes to be 64 char hex str, not {}".format(h)

        with DB() as db:
            transactions = db.tables.transactions
            comparison_col = transactions.block_hash if is_block_hashes else transactions.hash
            where_clause = or_(*[(comparison_col == h) for h in hashes])

            rows = transactions.select().where(where_clause).run(db.ex)
            if not rows:
                return None
            else:
                return [decode_tx(row['data']) for row in rows]

    @classmethod
    def _validate_block_link(cls, parent: dict, child: dict):
        """
        Validates the cryptographic integrity of the link between a connected parent and child block, as well as the
        integrity of each block individually.
        :param parent: The predecesor of the block 'child' in the blockchain.
        :param child: The child's previous_block_hash should point to the parent's hash
        :raises: An exception if validation fails
        """
        assert parent['number'] + 1 == child['number'], "Attempted to validate non-adjacent blocks\nparent={}\nchild={}" \
            .format(parent, child)

        # Ensure child links to parent
        if child['prev_block_hash'] != parent['hash']:
            raise InvalidBlockLinkException("Child block's previous hash does not point to parent!\nparent={}\nchild={}"
                                            .format(parent, child))

        for block in (parent, child):
            # We remove the 'hash'/'number' cols so we can reuse validate_block_data, which doesnt expect header cols
            block_hash = block.pop('hash')
            block_num = block.pop('number')

            # Only validate block data if it is not the genesis block
            if block_num != 1:
                cls.validate_block_data(block)

            # Ensure block data hashes to block hash
            expected_hash = cls.compute_block_hash(block)
            if expected_hash != block_hash:
                raise InvalidBlockHashException("hash(block_data) != block_hash for block number {}!".format(block_num))

    @classmethod
    def _decode_block(cls, block_data: dict) -> dict:
        """
        Takes a dictionary with keys for all columns in the block table, and returns the same dictionary but with any
        encoded values decoded. Currently, the only value being serialized is the 'block_contender' column.
        :param block_data: A dictionary, containing a key for each column in the blocks table. Some values might be encoded
        in a serialization format.
        :return: A dictionary, containing a key for each column in the blocks table.
        """
        # Convert block_contender back to a BlockContender instance
        block_data['block_contender'] = _deserialize_contender(block_data['block_contender'])

        return block_data

    @classmethod
    def _encode_block(cls, block_data: dict) -> dict:
        """
        Takes a dictionary with keys for all columns in the block table, and returns the same dictionary but with any
        non-serializable columns encoded. Currently, the only value being serialized is the 'block_contender' column.
        :param block_data: A dictionary, containing a key for each column in the blocks table.
        :return: A dictionary, containing a key for each column in the blocks table. Some values might be encoded
        in a serialization format.
        """
        # Convert block_contender to a serializable format
        block_data['block_contender'] = _serialize_contender(block_data['block_contender'])

        return block_data


# This needs to be declared below BlockStorageDriver class definition, as it uses a class function on BlockStorageDriver
# TODO put this in another file so hes not just chillin down here
GENESIS_HASH = BlockStorageDriver.compute_block_hash(GENESIS_BLOCK_DATA)
