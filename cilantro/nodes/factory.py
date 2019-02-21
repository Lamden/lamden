from cilantro.nodes.masternode.masternode import Masternode
from cilantro.nodes.delegate.delegate import Delegate
from cilantro.nodes.witness.witness import Witness
from cilantro.storage.contracts import seed_contracts
from cilantro.storage.redis import SafeRedis
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.constants.db_config import MONGO_DIR, config_mongo_dir
import  shutil


def _wait_for_redis():
    import redis, time
    r = redis.StrictRedis()
    while True:
        try:
            r = redis.StrictRedis()
            r.client_list()
            print("Redis ready!")
            break
        except:
            print("Waiting for Redis to be ready...")
            time.sleep(1)


def _wait_for_mongo():
    import time
    from pymongo import MongoClient
    while True:
        try:
            MongoClient()
            print("Mongo ready!")
            break
        except:
            print("Waiting for Mongo to be ready...")
            time.sleep(1)


def _drop_mongo():
    pass
    # print("Dropping MongoDB...")
    # dbs = ['mn_tx', 'mn_index', 'mn_store']
    # from pymongo import MongoClient
    # c = MongoClient()
    # for db in dbs:
    #     print("Dropping mongo table '{}'".format(db))
    #     c.drop_database(db)
    # shutil.rmtree(MONGO_DIR)
    # print("MongoDB dropped.")
    # config_mongo_dir()



class NodeFactory:
    @staticmethod
    def _reset_db():
        print("-------\tResetting database\t-------")
        SafeRedis.flushall()

    @staticmethod
    def _seed_if_necessary():
        indicator_key = 'contracts_code'  # if contracts are seeded, we expect this key to exist
        if not SafeRedis.exists(indicator_key):
            print("No contracts found in db. Seeding contracts")
            seed_contracts()
        else:
            print("Contracts already found in db. Skipping seeding.")

    @staticmethod
    def run_masternode(signing_key, ip, name='Masternode', reset_db=False):
        _wait_for_redis()
        _wait_for_mongo()
        if reset_db:
            NodeFactory._reset_db()
            _drop_mongo()
        NodeFactory._seed_if_necessary()
        MasterOps.init_master(key=signing_key)
        mn = Masternode(ip=ip, name=name, signing_key=signing_key)

    @staticmethod
    def run_witness(signing_key, ip, name='Witness', reset_db=False):
        _wait_for_redis()
        if reset_db:
            NodeFactory._reset_db()
        NodeFactory._seed_if_necessary()
        w = Witness(ip=ip, name=name, signing_key=signing_key)

    @staticmethod
    def run_delegate(signing_key, ip, name='Delegate', reset_db=False):
        _wait_for_redis()
        if reset_db:
            NodeFactory._reset_db()
        NodeFactory._seed_if_necessary()
        d = Delegate(ip=ip, name=name, signing_key=signing_key)
