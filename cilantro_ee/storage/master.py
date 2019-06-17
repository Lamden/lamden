import cilantro_ee
from pymongo import MongoClient, DESCENDING
from configparser import ConfigParser

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


class MasterStorage:
    BLOCK = 0
    INDEX = 1

    def __init__(self, config_path=cilantro_ee.__path__[0]):
        # Setup configuration file to read constants
        self.config_path = config_path

        self.config = ConfigParser()
        self.config.read(self.config_path + '/mn_db_conf.ini')

        user = self.config.get('MN_DB', 'username')
        password = self.config.get('MN_DB', 'password')
        port = self.config.get('MN_DB', 'port')

        block_database = self.config.get('MN_DB', 'mn_blk_database')
        index_database = self.config.get('MN_DB', 'mn_index_database')

        self.blocks = StorageSet(user, password, port, block_database, 'blocks')
        self.indexes = StorageSet(user, password, port, index_database, 'index')

    def q(self, v):
        if isinstance(v, int):
            return {'blockNum': v}
        return {'blockHash': v}

    def get_block(self, v):
        q = self.q(v)
        block = self.blocks.collection.find_one(q)

        if block is not None:
            block.pop('_id')

        return block

    def put(self, data, collection=BLOCK):
        if collection == MasterStorage.BLOCK:
            _id = self.blocks.collection.insert_one(data)
        elif collection == MasterStorage.INDEX:
            _id = self.indexes.collection.insert_one(data)
        else:
            return False

        return _id is not None

    def get_owners(self, v):
        q = self.q(v)
        index = self.indexes.collection.find_one(q)

        if index is None:
            return index

        owners = index.get('blockOwners')

        return owners

    def drop_collections(self):
        self.blocks.flush()
        self.indexes.flush()


class DistributedMasterStorage:
    pass

