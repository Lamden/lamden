import cilantro_ee
import os, time
import capnp
from configparser import SafeConfigParser, ConfigParser
from pymongo import MongoClient, DESCENDING
from cilantro_ee.utils.utils import MongoTools
from cilantro_ee.logger.base import get_logger
from cilantro_ee.messages.block_data.block_data import BlockData, MessageBase, GenesisBlockData
from cilantro_ee.protocol import wallet


class StorageSet:
    def __init__(self, user, password, port, database, collection_name):
        self.uri = 'mongodb://{}:{}@localhost:{}/{}?authSource=admin&maxPoolSize=1'.format(
            user,
            password,
            port,
            database
        )

        self.client = MongoClient(self.uri)
        self.db = self.client.get_database()
        self.collection = self.db[collection_name]

    def flush(self):
        self.client.drop_database(self.db)


class MasterDatabase:
    def __init__(self, signing_key, config_path=cilantro_ee.__path__[0]):
        # Setup signing and verifying key
        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)

        # Setup configuration file to read constants
        self.config_path = config_path

        self.config = ConfigParser()
        self.config.read(self.config_path+'/mn_db_conf.ini')

        user = self.config.get('MN_DB', 'username')
        password = self.config.get('MN_DB', 'password')
        port = self.config.get('MN_DB', 'port')

        block_database = self.config.get('MN_DB', 'mn_blk_database')
        index_database = self.config.get('MN_DB', 'mn_index_database')
        tx_database = self.config.get('MN_DB', 'mn_tx_database')

        # Setup database connection objects
        self.blocks = StorageSet(user, password, port, block_database, 'blocks')
        self.indexes = StorageSet(user, password, port, index_database, 'index')
        self.txs = StorageSet(user, password, port, tx_database, 'tx')

        if self.get_block_by_number(0) is None:
            self.create_genesis_block()

    def drop_db(self):
        self.blocks.flush()
        self.indexes.flush()

    def insert_block(self, block_dict=None):
        if block_dict is None:
            return False

        # insert passed dict block to db
        block_id = self.blocks.collection.insert_one(block_dict)

        if block_id:
            return True

    def get_block_by_number(self, block_number=None):
        block = self.blocks.collection.find_one({
            'blockNum': block_number
        })

        return block

    def get_block_by_hash(self, block_hash=None):
        block = self.blocks.collection.find_one({
            'blockHash': block_hash
        })

        return block

    def get_last_n_local_blocks(self, n=1):
        block_query = self.indexes.collection.find({}, {'_id': False}).sort(
            'blockNum', DESCENDING
        ).limit(n)

        blocks = [block for block in block_query]

        if len(blocks) > 1:
            first_block_num = blocks[0].get('blockNum')
            last_block_num = blocks[-1].get('blockNum')

            assert first_block_num > last_block_num, "Blocks are not descending."

        return blocks

    def get_block_owners(self, block_number=None, block_hash=None):
        if block_number is not None:
            query = {
                'blockNum': block_number
            }
        elif block_hash is not None:
            query = {
                'blockHash': block_hash
            }
        else:
            return None

        block = self.indexes.collection.find_one(query)

        if block is None:
            return None

        owners = block.get('blockOwners')
        return owners

    def create_genesis_block(self):
        block = GenesisBlockData.create(sk=self.signing_key, vk=self.verifying_key)
        _id = self.insert_block(block.to_dict())

        assert _id, 'Failed to create Genesis Block'
