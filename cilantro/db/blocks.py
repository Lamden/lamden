from cilantro.logger import get_logger
import seneca.seneca_internal.storage.easy_db as t
from cilantro.db.tables import create_table
from cilantro.messages import BlockContender, TransactionBase
from cilantro.utils import is_valid_hex, Hasher
from cilantro.protocol.structures import MerkleTree
from cilantro.protocol.wallets.wallet import Wallet
from cilantro.db import DB
from cilantro.db.transactions import encode_tx, decode_tx
from typing import List
import time


log = get_logger("BlocksStorage")


"""
Block Data fields


REQUIRED_COLS must exist in all Cilantro based blockchains
Custom Cilantro configurations can configure OPTIONAL_COLS to add additional fields to block metadata
"""
REQUIRED_COLS = {'merkle_root': str, 'merkle_leaves': str, 'prev_block_hash': str, 'block_contender': str}  # TODO block_contender should be binary blob
OPTIONAL_COLS = {'timestamp': int, 'masternode_signature': str, 'masternode_vk': str}

BLOCK_DATA_COLS = {**REQUIRED_COLS, **OPTIONAL_COLS}  # combines the 2 dictionaries


"""
Genesis Block default values
"""
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
    def store_block(cls, block_contender: BlockContender, raw_transactions: List[bytes], publisher_sk: str, timestamp: int = 0):
        """

        Persist a new block to the blockchain, along with the raw transactions associated with the block. An exception
        will be raised if an error occurs either validating the new block data, or storing the block. Thus, it is
        recommended that this method is wrapped in a try block.

        :param block_contender: A BlockContender instance
        :param raw_transactions: A list of ordered raw transactions contained in the block
        :param publisher_sk: The signing key of the publisher (a Masternode) who is publishing the block
        :param timestamp: The time the block was published, in unix epoch time. If 0, time.time() is used
        :return: None
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

        publisher_vk = Wallet.get_vk(publisher_sk)
        publisher_sig = Wallet.sign(publisher_sk, tree.root)

        # Build and validate block_data
        block_data = {
            'block_contender': block_contender,
            'timestamp': timestamp,
            'merkle_root': tree.root_as_hex,
            'merkle_leaves': tree.leaves_as_concat_hex_str,
            'prev_block_hash': cls._get_latest_block_hash(),
            'masternode_signature': publisher_sig,
            'masternode_vk': publisher_vk,
        }
        cls._validate_block_data(block_data)

        # Compute block hash
        block_hash = cls._compute_block_hash(block_data)

        # Encode block data for serialization and finally persist the data
        log.info("Attempting to persist new block with hash {}".format(block_hash))
        block_data = cls._encode_block(block_data)

        with DB() as db:
            # Store block
            res = db.tables.blocks.insert([{'hash': block_hash, **block_data}]).run(db.ex)
            if res:
                log.info("Successfully inserted new block with number {} and hash {}".format(res['last_row_id'], block_hash))
            else:
                log.error("Error inserting block! Got None/False result back from insert query. Result={}".format(res))
                return

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

    @classmethod
    def get_block(cls, number: int=0, hash: str='') -> dict or None:
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
                return cls._decode_block(block[0]) if block else None

    @classmethod
    def get_latest_block(cls) -> dict:
        """
        Retrieves the latest block published in the chain.
        :return: A dictionary representing the latest block, containing a key for each column in the blocks table.
        """
        with DB() as db:
            latest = db.tables.blocks.select().order_by('number', desc=True).limit(1).run(db.ex)
            assert latest, "No blocks found! There should be a genesis. Was the database properly seeded?"
            return cls._decode_block(latest[0])

    @classmethod
    def get_raw_transaction(cls, tx_hash: str) -> bytes or None:
        """
        Retrieves a single raw transaction from its hash. Returns None if no transaction for that hash can be found
        :param tx_hash: The hash of the raw transaction to lookup. Should be a 64 character hex string
        :return: The raw transactions as bytes, or None if no transaction with that hash can be found
        """
        assert is_valid_hex(tx_hash, length=64), "Expected tx_hash to be 64 char hex str, not {}".format(tx_hash)

        with DB() as db:
            transactions = db.tables.transactions
            rows = transactions.select().where(transactions.hash == tx_hash).run(db.ex)
            if not rows:
                return None
            else:
                assert len(rows) == 1, "Multiple Transactions found with has {}! BIG TIME DEVELOPMENT ERROR!!!".format(tx_hash)
                return decode_tx(rows[0]['data'])

    @classmethod
    def get_raw_transactions_from_block(cls, block_hash: str) -> List[bytes] or None:
        """
        Retrieves a list of raw transactions associated with a particular block. Returns None if no block with
        the given hash can be found.
        :param block_hash:
        :return: A list of raw transactions each as bytes, or None if no block with the given hash can be found
        """
        assert is_valid_hex(block_hash, length=64), "Expected block_hash to be 64 char hex str, not {}".format(block_hash)

        with DB() as db:
            transactions = db.tables.transactions
            rows = transactions.select().where(transactions.block_hash == block_hash).run(db.ex)
            if not rows:
                return None
            else:
                return [decode_tx(row['data']) for row in rows]

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
    def _validate_block_link(cls, parent: dict, child: dict):
        """
        Validates the cryptographic integrity of the link between a connected parent and child block, as well as the
        integrity of each block individually.
        :param parent: The predecesor of the block 'child' in the blockchain.
        :param child: The child's previous_block_hash should point to the parent's hash
        :raises: An exception if validation fails
        """
        assert parent['number'] + 1 == child['number'], "Attempted to validate non-adjacent blocks\nparent={}\nchild={}"\
                                                        .format(parent, child)

        # Ensure child links to parent
        if child['prev_block_hash'] != parent['hash']:
            raise InvalidBlockLinkException("Child block's previous hash does not point to parent!\nparent={}\nchild={}"
                                            .format(parent, child))

        for block in (parent, child):
            # We remove the 'hash'/'number' cols so we can reuse _validate_block_data, which doesnt expect header cols
            block_hash = block.pop('hash')
            block_num = block.pop('number')

            # Only validate block data if it is not the genesis block
            if block_num != 1:
                cls._validate_block_data(block)

            # Ensure block data hashes to block hash
            expected_hash = cls._compute_block_hash(block)
            if expected_hash != block_hash:
                raise InvalidBlockHashException("hash(block_data) != block_hash for block number {}!".format(block_num))

    @classmethod
    def _validate_block_data(cls, block_data: dict):
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

        # TODO validate MerkleSignatures are infact signed by valid delegates
        # this is tricky b/c we would need to know who the delegates were at the time of the block, not necessarily the
        # current delegates

        # Validate Masternode Signature
        if not is_valid_hex(block_data['masternode_vk'], length=64):
            raise InvalidBlockSignatureException("Invalid verifying key for field masternode_vk: {}"
                                                 .format(block_data['masternode_vk']))
        if not Wallet.verify(block_data['masternode_vk'], bytes.fromhex(block_data['merkle_root']), block_data['masternode_signature']):
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
GENESIS_HASH = BlockStorageDriver._compute_block_hash(GENESIS_BLOCK_DATA)
