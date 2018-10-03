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
            cls.mn_db = MongoClient(uri).get_database()
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
            cls.log.info("uri {}".format(uri))
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
            block_dict = cls.unpack_block(block = cls.blk_zero)
            cls.log.info("genesis block {}".format(block_dict))
            #blk_id = cls.mn_collection.insert_one(block_dict).inserted_id
            cls.init_mdb = True
            #return blk_id
        else:
            # insert passed dict block to db
            blk_id = cls.mn_collection.insert(block_dict)
            return blk_id

        return False

    @classmethod
    def unpack_block(cls, block=None):
        if not block:
            return
        blk_hash = block.block_hash
        blk_num =  block.block_num
        blk_in_hash = block.input_hashes
        blk_prev_hash = block.prev_block_hash
        blk_ms = block.masternode_signature
        blk_tx = block.transactions

        block_dict = {'block_num':blk_num, 'block_hash' : blk_hash, 'prev_block_hash' : blk_prev_hash,
                     'input_hashes' : blk_in_hash, 'master_sig' : blk_ms, 'transactions' : blk_tx}

        return block_dict

    def query_db_status(self, list='all'):

        # db_list = self.mn_client.list_database_names() + self.stash_client.list_database_names()
        # if list == 'all':
        #     return db_list
        pass