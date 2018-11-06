import cilantro, os
from configparser import SafeConfigParser
from pymongo import MongoClient
from cilantro.logger.base import get_logger
from cilantro.messages.block_data.block_data import BlockDataBuilder, BlockData
from cilantro.storage.driver import BlockMetaSQL

class MDB():
    # Config
    log = get_logger("mdb_log")
    path = os.path.dirname(cilantro.__path__[0])
    cfg = SafeConfigParser()
    cfg.read('{}/mn_db_conf.ini'.format(path))

    # mongo setup
    user=cfg.get('MN_DB','username')
    pwd=cfg.get('MN_DB','password')
    port=cfg.get('MN_DB','port')

    mn_client = None
    mn_db = None
    mn_collection = None
    init_mdb = False
    blk_zero = None

    def __init__(self, Type=None, reset=False):
        if self.init_mdb == False:
            self.start_db(Type='all')
            return

        if reset==True and self.init_mdb==True:
            self.reset_db(db=Type)
            return


    @classmethod
    def start_db(cls,Type="all"):
        """
            init block store, store_index
        """
        if Type=='new' or Type=='all':
            uri = MDB.setup_db()
            cls.mn_client = MongoClient(uri)
            cls.mn_db = cls.mn_client['blocks']
            cls.mn_collection = cls.mn_db['chains']
            cls.init_mdb = cls.insert_record()
            #blk_id = cls.mn_collection.insert_one(first)
            #cls.log.info("insert id {}".format(blk_id))

        if Type=='cache' or Type=='all':
            uri = cls.setup_db(Type='cache')
            stash_client = MongoClient(uri)
            collection = stash_client["index"]


    @classmethod
    def setup_db(cls,Type='new'):
        if Type == 'new':    # fresh setup
            database = cls.cfg.get('MN_DB','mn_blk_database')
            uri="mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin"
            return uri

        if Type == 'cache':
            database = cls.cfg.get('MN_DB','mn_cache_database')
            uri="mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin"
            return uri

    @classmethod
    def reset_db (cls, db='all'):
        if db == all:
            cls.mn_client.drop_database()

        cls.start_db()

    @classmethod
    def insert_record(cls, block_dict=None):
        if cls.init_mdb == False:
            cls.blk_zero = BlockDataBuilder.create_block()
            cls.log.info("genesis block {}".format(cls.blk_zero))

            # block_dict = cls.unpack_block(cls.blk_zero)
            # cls.log.info("genesis block {}".format(block_dict))
            #blk_id = cls.mn_collection.insert(block_dict)
            cls.init_mdb = True
            #return blk_id
        else:
            # insert passed dict block to db
            blk_id = cls.mn_collection.insert(block_dict)
            return blk_id

        return False

    @classmethod
    def unpack_block(cls, block=None):
        if block == None:
            return
        blk_hash = BlockData.block_hash(block[0])
        blk_num = BlockData.block_num(block[1])
        blk_in_hash = BlockData.input_hashes(block[2])
        blk_prev_hash = BlockData.prev_block_hash(block[3])
        blk_ms = BlockData.masternode_signature(block[4])
        blk_tx = BlockData.transactions(block[5])

        cls.log.info("decoded block_hash {}".format(blk_hash))
        cls.log.info("decoded block_hash {}".format(blk_hash))
        cls.log.info("decoded block_hash {}".format(blk_hash))

    def query_db_status(self, list='all'):

        # db_list = self.mn_client.list_database_names() + self.stash_client.list_database_names()
        # if list == 'all':
        #     return db_list
        pass