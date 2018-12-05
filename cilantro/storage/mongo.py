import cilantro
import os
import capnp
from configparser import SafeConfigParser
from pymongo import MongoClient
from cilantro.utils.utils import MongoTools
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

    '''
        data base mgmt functionality
    '''
    @classmethod
    def start_db(cls):
        """
            init block store, store_index
        """
        if cls.init_mdb is False:
            uri = cls.setup_db(db_type = 'MDB')
            cls.mn_client = MongoClient(uri)
            cls.mn_db = cls.mn_client.get_database()
            block = BlockDataBuilder.create_block(blk_num=0)
            #print("just created block {}".format(block))
            cls.genesis_blk = cls.get_dict(capnp_struct = block)
            #cls.log.spam("storing genesis block... {}".format(cls.genesis_blk))
            cls.mn_collection = cls.mn_db['blocks']
            cls.init_mdb = cls.insert_record(block_dict=cls.genesis_blk)

            cls.log.debug('flipping the bit {}'.format(cls.init_mdb))

            if cls.init_mdb is True:
                uri = cls.setup_db(db_type = 'index')
                cls.mn_client_idx = MongoClient(uri)
                cls.mn_db_idx = MongoClient(uri).get_database()
                cls.mn_coll_idx = cls.mn_db_idx['index']
                idx = {'blockNum': cls.genesis_blk.get('blockNum'), 'blockHash': cls.genesis_blk.get('blockHash'),
                       'mn_sign': cls.genesis_blk.get('masternodeSignature')}
                cls.log.debug('print index {}'.format(idx))

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


    '''
        Wr to store or index
    '''
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
    def insert_idx_record(cls, my_dict=None):
        if dict is None:
            return None
        idx_entry = cls.mn_coll_idx.insert(my_dict)
        cls.log.info("entry {}".format(idx_entry))
        return True

    # move this to util
    @classmethod
    def get_dict(cls, capnp_struct):
        obj = capnp_struct._data.to_dict()

        bk_hsh = capnp_struct._data.blockHash.decode()
        cls.log.info("test blk_hash{}".format(bk_hsh))
        if isinstance(capnp_struct, BlockData):
            obj['transactions'] = capnp_struct.indexed_transactions
        return obj

    '''
        reading from index or store
    '''

    @classmethod
    def query_index(cls, n_blks=None):
        if n_blks is None:
            return
        blk_dict = {}

        blk_delta = cls.mn_coll_idx.find().limit(n_blks).sort("blockNum", -1)
        for blk in blk_delta:
            cls.log.info('requested block delta {}'.format(blk))
            blk_dict.update(blk)

        cls.log.debug("return dict {}".format(blk_dict))
        l = MongoTools.get_results(data = blk_delta)
        cls.log.debug("testing dump util {}".format(l))
        return blk_dict

    @classmethod
    def query_db(cls, type=None, query=None):
        if query is None:
            if type is None or type is "MDB":
                block_list = cls.mn_collection.find({})
                for x in block_list:
                    cls.log.info("{}".format(x))

            if type is None or type is "index":
                index_list = cls.mn_coll_idx.find({})
                for y in index_list:
                    cls.log.info("{}".format(y))
            return

        if type is 'idx' and query is not None:
            result = cls.mn_coll_idx.find(query)
            MongoTools.get_results(result)
            cls.log.info("count {}".format(MongoTools.get_count(result)))
            for x in result:
                cls.log.info("result {}".format(x))
            return result

        if type is 'MDB' and query is not None:
            result = cls.mn_collection.find(query)
            for x in result:
                cls.log.info("result {}".format(x))
            return result

    @classmethod
    def query_store(cls, blk_num = None):
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
