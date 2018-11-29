import cilantro
import os
from configparser import SafeConfigParser
from pymongo import MongoClient
from cilantro.logger.base import get_logger
from cilantro.messages.block_data.block_data import BlockDataBuilder, BlockData, MessageBase


class MDB:
    # Config
    log = get_logger("mdb_log")
    path = os.path.dirname(cilantro.__path__[0])
    cfg = SafeConfigParser()
    cfg.read('{}/mn_db_conf.ini'.format(path))

    # Mongo setup
    user = cfg.get('MN_DB', 'username')
    pwd = cfg.get('MN_DB', 'password')
    port = cfg.get('MN_DB', 'port')

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

    def __init__(self, reset=False):
        if self.init_mdb is False:
            self.start_db()
            return

        if reset is True and self.init_mdb is True:
            self.reset_db(db='all')
            return

    @classmethod
    def start_db(cls):
        """
            init block store, store_index
        """
        if cls.init_mdb is False:
            uri = cls.setup_db(db_type = 'MDB')
            cls.mn_client = MongoClient(uri)
            cls.mn_db = cls.mn_client.get_database()

            block = BlockDataBuilder.create_block(blk_num = 0)
            #print("just created block {}".format(block))
            cls.genesis_blk = cls.get_dict(capnp_struct = block)
            cls.log.spam("storing genesis block... {}".format(cls.genesis_blk))
            cls.mn_collection = cls.mn_db['blocks']
            cls.init_mdb = cls.insert_record(cls.genesis_blk)

            if cls.init_mdb is True:
                uri = cls.setup_db(db_type = 'index')
                cls.mn_client_idx = MongoClient(uri)
                cls.mn_db_idx = MongoClient(uri).get_database()
                cls.mn_coll_idx = cls.mn_db_idx['index']
                idx = {'block_num': cls.genesis_blk.get('block_num'), 'block_hash': cls.genesis_blk.get('block_hash'),
                       'mn_sign': cls.genesis_blk.get('mn_sign')}
                cls.init_idx_db = cls.insert_idx_record(my_dict=idx)

    @classmethod
    def setup_db(cls, db_type=None):
        if db_type == 'MDB':    # fresh setup
            database = cls.cfg.get('MN_DB', 'mn_blk_database')
            uri = "mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin"
            cls.log.info("uri {}".format(uri))
            return uri

        if db_type == 'index':
            database = cls.cfg.get('MN_DB', 'mn_index_database')
            uri = "mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin"
            return uri

    @classmethod
    def reset_db(cls, db='all'):
        cls.drop_db(db)
        cls.start_db()

    @classmethod
    def drop_db(cls, db='all'):
        if db == 'all':
            cls.mn_client.drop_database(cls.mn_db)
            cls.mn_client_idx.drop_database(cls.mn_db_idx)
            cls.init_mdb = cls.init_idx_db = False

    @classmethod
    def insert_record(cls, block_dict=None):
        if block_dict is None:
            return False

        # insert passed dict block to db
        blk_id = cls.mn_collection.insert(block_dict)
        # cls.log.info("block {}".format(block_dict))
        if blk_id:
            return True

    @classmethod
    def insert_idx_record(cls, my_dict = None):
        if dict is None:
            return None
        idx_entry = cls.mn_coll_idx.insert(my_dict)
        cls.log.info("entry {}".format(idx_entry))
        return True

    @classmethod
    def get_dict(cls, capnp_struct, ignore=[]):
        #assert issubclass(type(capnp_struct), MessageBase), "Expected a MessageBase subclass not {}".format(type(capnp_struct))
        ignore = set(ignore)
        return capnp_struct._data.to_dict()

    def query_db(self, type=None, query=None):

        if query is None:
            if type is None or type is "MDB":
                block_list = self.mn_collection.find({})
                for x in block_list:
                    self.log.info("{}".format(x))

            if type is None or type is "index":
                index_list = self.mn_coll_idx.find({})
                for y in index_list:
                    self.log.info("{}".format(y))
            return

        if type is 'idx' and query is not None:
            result = self.mn_coll_idx.find(query)
            for x in result:
                self.log.info("result {}".format(x))
            return result
