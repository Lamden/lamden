import cilantro, os
from configparser import SafeConfigParser
from pymongo import MongoClient
from cilantro.messages.block_data.block_data import BlockDataBuilder

class MDB():
    path = os.path.dirname(cilantro.__path__[0])
    cfg = SafeConfigParser()
    cfg.read('{}/mn_db_conf.ini'.format(path))

    user=cfg.get('MN_DB','username')
    pwd=cfg.get('MN_DB','password')
    port=cfg.get('MN_DB','port')
    blk_zero = BlockDataBuilder.create_block()

    def start_db(self, Type="all"):
        """
            init block store, store_index
        """
        if Type=='new' or Type=='all':
            uri = self.setup_db()
            self.perennial_client = MongoClient(uri)
            self.db = self.perennial_client['blocks']
            self.collection = self.db['chains']
        #    self.first = BlockData._deserialize_data(self.blk_zero)
            self.blkid = self.collection.insert_one(self.first)


        if Type=='cache' or Type=='all':
            uri = self.setup_db(Type='cache')
            self.stash_client = MongoClient(uri)
            self.collection = self.stash_client["index"]

    @classmethod
    def setup_db(cls,Type='new'):

        if Type == 'new':    # fresh setup
            database = cls.cfg.get('MN_DB','mn_blk_database')
            uri="mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin"
            return uri, database

        if Type == 'cache':
            database = cls.cfg.get('MN_DB','mn_cache_database')
            uri="mongodb://"+cls.user+":"+cls.pwd+"@localhost:"+cls.port+'/'+database+"?authSource=admin"
            return uri, database

    @classmethod
    def reset_db (cls, db='all'):
        if db == all:
            cls.perennial_client.drop_database()
#            cls.stash_client.drop_database()

        cls.start_db()

    @classmethod
    def insert_record(cls, info):
        pass

    def query_db_status(self, list='all'):

        db_list = self.perennial_client.list_database_names() + self.stash_client.list_database_names()
        if list == 'all':
            return db_list
