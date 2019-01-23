from cilantro.nodes.masternode.masternode import Masternode
from cilantro.nodes.delegate.delegate import Delegate
from cilantro.nodes.witness.witness import Witness
from cilantro.storage.contracts import seed_contracts
from cilantro.storage.mongo import MDB
from cilantro.nodes.masternode.master_store import MasterOps
from seneca.engine.interface import SenecaInterface
from cilantro.storage.vkbook import VKBook

from cilantro.constants.overlay_network import HOST_IP


def _wait_for_redis():
    import redis, time
    r = redis.StrictRedis()
    while True:
        try:
            r = redis.StrictRedis()
            print("Redis ready!")
            r.client_list()
            break
        except:
            print("Waiting for Redis to be ready...")
        time.sleep(1)


def _wait_for_mongo():
    import redis, time
    from pymongo import MongoClient
    while True:
        try:
            MongoClient()
            break
        except:
            print("Mongo ready!")
            print("Waiting for Mongo to be ready...")
        time.sleep(1)


class NodeFactory:
    @staticmethod
    def _reset_db():
        with SenecaInterface() as interface:
            interface.r.flushall()
        seed_contracts()

    @staticmethod
    def run_masternode(signing_key, ip, name='Masternode', reset_db=False):
        _wait_for_redis()
        _wait_for_mongo()
        if reset_db:
            NodeFactory._reset_db()
        MasterOps.init_master(key=signing_key)
        mn = Masternode(ip=ip, name=name, signing_key=signing_key)

    @staticmethod
    def run_witness(signing_key, ip, name='Witness', reset_db=False):
        _wait_for_redis()
        if reset_db: NodeFactory._reset_db()
        w = Witness(ip=ip, name=name, signing_key=signing_key)

    @staticmethod
    def run_delegate(signing_key, ip, name='Delegate', reset_db=False):
        _wait_for_redis()
        if reset_db: NodeFactory._reset_db()
        d = Delegate(ip=ip, name=name, signing_key=signing_key)
