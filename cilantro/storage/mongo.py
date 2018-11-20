import cilantro, os, ujson as json, bson
from configparser import SafeConfigParser
from pymongo import MongoClient
from cilantro.logger.base import get_logger
from cilantro.messages.block_data.block_data import BlockDataBuilder, BlockData

class MDB():
    # Config
    log = get_logger("mdb_log")
    path = os.path.dirname(cilantro.__path__[0])
    cfg = SafeConfigParser()
    cfg.read('{}/mn_db_conf.ini'.format(path))

    # mongo setup
    user = cfg.get('MN_DB','username')
    pwd = cfg.get('MN_DB','password')
    port = cfg.get('MN_DB','port')

    mn_client = None
    mn_db = None
    _is_setup = False
    genesis_blk = None

    def __init__(self, db_type=None, reset=False):
        if self._is_setup == False:
            self.start_db(db_type='all')
            return

        if reset==True and self._is_setup == True:
            self.reset_db(db=db_type)
            return

    @classmethod
    def start_db(cls,db_type="all"):
        """
            init block store, store_index
        """
        if db_type=='new' or db_type=='all':
            uri = MDB.setup_db()
            cls.mn_client = MongoClient(uri)
            cls.mn_db = cls.mn_client.get_database()
            cls.genesis_blk = BlockDataBuilder.create_block()
            block_dict = cls.get_dict(cls.genesis_blk)

            cls.log.spam("storing genesis block... {}".format(block_dict))
            blk_id = cls.mn_db['blocks'].insert_one(block_dict)
            cls._is_setup = True
            return blk_id

        if db_type=='cache' or db_type=='all':
            uri = cls.setup_db(db_type='cache')
            stash_client = MongoClient(uri)
            collection = stash_client["index"]


    @classmethod
    def setup_db(cls, db_type='new'):
        if db_type == 'new':    # fresh setup
            database = cls.cfg.get('MN_DB','mn_blk_database')
            uri="mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin"
            cls.log.info("uri {}".format(uri))
            return uri

        if db_type == 'cache':
            database = cls.cfg.get('MN_DB','mn_cache_database')
            uri="mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin"
            return uri

    @classmethod
    def reset_db(cls, db='all'):
        cls.drop_db(db)
        cls.start_db()

    @classmethod
    def drop_db(cls, db='all'):
        pass # TODO, doesn't work!
        # if db == 'all':
        #     cls.mn_client.drop_database(cls.mn_db)

    @classmethod
    def get_dict(cls, capnp_struct, ignore=[]):
        d = {}
        ignore = set(ignore)
        for k,v in capnp_struct.__class__.__dict__.items():
            if k in ignore: continue
            val = getattr(capnp_struct, k)
            if type(v) == property:
                if type(val) == list:
                    if hasattr(val[0], 'serialize'):
                        val = [v_i.serialize() for v_i in val]
                elif hasattr(val, 'serialize'):
                    val = val.serialize()
                d[k] = val
        return d

    def query_db_status(self, list='all'):
        # db_list = self.mn_client.list_database_names() + self.stash_client.list_database_names()
        # if list == 'all':
        #     return db_list
        pass
