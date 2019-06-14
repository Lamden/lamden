import cilantro_ee
import os, time
import capnp
from configparser import SafeConfigParser, ConfigParser
from pymongo import MongoClient, DESCENDING
from cilantro_ee.utils.utils import MongoTools
from cilantro_ee.logger.base import get_logger
from cilantro_ee.messages.block_data.block_data import BlockData, MessageBase
from cilantro_ee.protocol import wallet


class MasterDatabase:
    def __init__(self, signing_key, config_path=cilantro_ee.__path__[0]):
        # Setup signing and verifying key
        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)

        # Setup configuration file to read constants
        self.config_path = config_path

        self.config = ConfigParser()
        self.config.read(self.config_path+'/mn_db_conf.ini')

        self.block_client = None
        self.block_db = None
        self.block_collection = None

        self.index_client = None
        self.index_db = None
        self.index_collection = None

        self.tx_client = None
        self.tx_db = None
        self.tx_collection = None

        self.setup_db()

    def setup_db(self):

        # Setup the DB
        user = self.config.get('MN_DB', 'username')
        password = self.config.get('MN_DB', 'password')
        port = self.config.get('MN_DB', 'port')
        block_database = self.config.get('MN_DB', 'mn_blk_database')

        URI = 'mongodb://{}:{}@localhost:{}/{}?authSource=admin&maxPoolSize=1'
        block_uri = URI.format(user, password, port, block_database)

        self.block_client = MongoClient(block_uri)
        self.block_db = self.block_client.get_database()
        self.block_collection = self.block_db['blocks']

        index_database = self.config.get('MN_DB', 'mn_index_database')
        index_uri = URI.format(user, password, port, index_database)

        self.index_client = MongoClient(index_uri)
        self.index_db = self.index_client.get_database()
        self.index_collection = self.index_db['index']

        tx_database = self.config.get('MN_DB', 'mn_tx_database')
        tx_uri = URI.format(user, password, port, tx_database)

        self.tx_client = MongoClient(tx_uri)
        self.tx_db = self.tx_client.get_database()
        self.tx_collection = self.tx_db['tx']

    def drop_db(self):
        self.block_client.drop_database(self.block_db)
        self.index_client.drop_database(self.index_db)

    def reset_db(self):
        self.drop_db()
        self.setup_db()

    def insert_block(self, block_dict=None):
        if block_dict is None:
            return False

        # insert passed dict block to db
        block_id = self.block_collection.insert_one(block_dict)

        if block_id:
            return True


class MDB:
    # Config
    log = get_logger("mdb_log")
    path = os.path.dirname(cilantro_ee.__path__[0])
    cfg = SafeConfigParser()
    cfg.read('{}/mn_db_conf.ini'.format(path))

    # Mongo setup
    user = cfg.get('MN_DB', 'username')
    pwd = cfg.get('MN_DB', 'password')
    port = cfg.get('MN_DB', 'port')

    # master
    sign_key = None
    verify_key = None
    # master store db

    mn_client = None
    mn_db = None
    mn_collection = None
    genesis_blk = None
    init_mdb = False

    # local index db

    mn_client_idx = None
    mn_db_idx = None
    mn_coll_idx = None
    init_idx_db = False

    # local tx db

    mn_client_tx = None
    mn_db_tx = None
    mn_coll_tx = None
    init_tx_db = False

    def __init__(self, s_key):
        if self.init_mdb is False:
            MDB.sign_key = s_key
            MDB.verify_key = wallet.get_vk(s_key)
            self.start_db()
            return

        # if prior_state_found is True and self.init_mdb is True:
        #     self.reset_db(db='all')
        #     return

    '''
        data base mgmt functionality
    '''
    @classmethod
    def start_db(cls):
        """
            init block store, store_index
        """
        if cls.init_mdb is False:
            # Sleep to prevent race conditions with create_user in the start_mongo.sh scripts.
            # we only do this on containers
            # time.sleep(5)  # doesnt seem like we need this --davis
            pass

        cls.setup_db()

        prev_idx = cls.query_index(n_blks = 1)
        # cls.log.important('prev idx {}'.format(prev_idx))
        if len(prev_idx) == 0:
            cls.init_idx_db = cls.create_genesis_blk()
        else:
            cls.init_mdb = True
            cls.init_idx_db = True
            cls.init_tx_db = True

        assert cls.init_idx_db is True, "failed to init index table"

    @classmethod
    def setup_db(cls):
        database = cls.cfg.get('MN_DB', 'mn_blk_database')
        store_uri = "mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin&maxPoolSize=1"
        cls.log.debugv("store uri {}".format(store_uri))
        cls.mn_client = MongoClient(store_uri)
        cls.mn_db = cls.mn_client.get_database()
        cls.mn_collection = cls.mn_db['blocks']

        database = cls.cfg.get('MN_DB', 'mn_index_database')
        index_uri = "mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin&maxPoolSize=1"
        cls.log.debugv("index uri {}".format(index_uri))
        cls.mn_client_idx = MongoClient(index_uri)
        cls.mn_db_idx = cls.mn_client_idx.get_database()
        cls.mn_coll_idx = cls.mn_db_idx['index']

        database = cls.cfg.get('MN_DB', 'mn_tx_database')
        tx_uri = "mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin&maxPoolSize=1"
        cls.log.debugv("index uri {}".format(tx_uri))
        cls.mn_client_tx = MongoClient(tx_uri)
        cls.mn_db_tx = cls.mn_client_tx.get_database()
        cls.mn_coll_tx = cls.mn_db_tx['tx']

    @classmethod
    def create_genesis_blk(cls):

        # create insert genesis blk
        block = GenesisBlockData.create(sk = cls.sign_key, vk = cls.verify_key)
        cls.init_mdb = cls.insert_block(block_dict=block._data.to_dict())
        assert cls.init_mdb is True, "failed to create genesis block"

        cls.log.debugv('start_db init set {}'.format(cls.init_mdb))

        # update index record
        if cls.init_mdb is True:
            idx = {'blockNum': block.block_num, 'blockHash': block.block_hash, 'blockOwners': cls.verify_key,
                   'ts': time.time()}
            cls.log.debugv('start_db init index {}'.format(idx))
            return cls.insert_idx_record(my_dict = idx)

    @classmethod
    def reset_db(cls, db='all'):
        cls.drop_db(db)
        cls.start_db()

    @classmethod
    def drop_db(cls, db='all'):
        if db == 'all':
            cls.log.important("Dropping all mongo databases")
            cls.mn_client.drop_database(cls.mn_db)
            cls.mn_client_idx.drop_database(cls.mn_db_idx)
            cls.init_mdb = cls.init_idx_db = False

    '''
        Wr to store or index
    '''
    @classmethod
    def insert_block(cls, block_dict=None):
        if block_dict is None:
            return False

        # insert passed dict block to db
        blk_id = cls.mn_collection.insert_one(block_dict)
        cls.log.spam("block {}".format(block_dict))
        if blk_id:
            return True

    @classmethod
    def insert_idx_record(cls, my_dict=None):
        if dict is None:
            return None
        idx_entry = cls.mn_coll_idx.insert_one(my_dict)
        cls.log.spam("insert_idx_record -> {}".format(idx_entry))
        return True

    @classmethod
    def insert_tx_map(cls, txmap):
        obj = cls.mn_coll_tx.insert_one(txmap)
        cls.log.debugv("insert_idx_record -> {}".format(obj))

    '''
        reading from index or store
    '''
    @classmethod
    def query_index(cls, n_blks=None):
        """
        Queries index table for last n blocks, builds list of dict in ascending order for response
        :param n_blks:
        :return: list of dict in descending order
        """
        blk_list = []

        blk_delta = cls.mn_coll_idx.find({}, {'_id': False}).sort("blockNum", DESCENDING).limit(n_blks)
        for blk in blk_delta:
            cls.log.spam('query_index block delta {}'.format(blk))
            blk_list.append(blk)

        cls.log.debugv("query_index returning dict {}".format(blk_list))
        if len(blk_list) > 1:
            assert blk_list[0].get('blockNum') > blk_list[-1].get('blockNum'), \
                "we expect blk list to be in descending"
        return blk_list

    @classmethod
    def query_db(cls, type=None, query=None):
        result = {}
        if query is None:
            if type is None or type is "MDB":
                block_list = cls.mn_collection.find({})
                for x in block_list:
                    result.update(x)
                    cls.log.spam("from mdb {}".format(x))

            if type is None or type is "idx":
                index_list = cls.mn_coll_idx.find({})
                for y in index_list:
                    result.update(y)
                    cls.log.spam("from idx {}".format(y))
        else:
            if type is 'idx':
                dump = cls.mn_coll_idx.find(query)
                cls.log.debug("Mongo tools count {}".format(MongoTools.get_count(dump)))
                assert MongoTools.get_count(dump) != 0, "lookup failed count is 0 dumping result-{} n query-{}"\
                    .format(dump, query)
                for x in dump:
                    result.update(x)
                cls.log.debug("result {}".format(result))

            if type is 'MDB':
                outcome = cls.mn_collection.find(query)
                for x in outcome:
                    result.update(x)
                    cls.log.spam("result {}".format(x))

            if type is 'tx':
                outcome = cls.mn_coll_tx.find(query)
                count = 0
                for x in outcome:
                    # cls.log.important2("RESULT X {} count {}".format(x, MongoTools.get_count(result)))
                    result.update(x)
                    count = count + 1
                # assert result != 1, "we have duplicate transactions dumping result {}".format(result)
                if count > 1:
                    cls.log.error("we have duplicate transaction results {}".format(result))

        if len(result) > 0:
            # cls.log.important("result => {}".format(result))
            return result
        else:
            cls.log.spam("result => {}".format(result))
            return None

    @classmethod
    def query_store(cls, blk_num=None):
        """
        Returns locally stored block by blk_num
        :param blk_num:
        :return:
        """
        response = cls.mn_collection.find(blk_num)

        if response is None:
            cls.log.error('given blk not present in db')
            return

        return response
