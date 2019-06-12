from cilantro_ee.nodes.masternode.masternode import Masternode
from cilantro_ee.nodes.delegate.delegate import Delegate
from cilantro_ee.storage.driver import SafeDriver
from cilantro_ee.nodes.masternode.master_store import MasterOps
from cilantro_ee.constants.conf import CilantroConf

MASTERNODE = 0
DELEGATE = 1
WITNESS = 2


def _wait_for_redis():
    import time
    time.sleep(20)


def _wait_for_mongo():
    import time
    from pymongo import MongoClient
    while True:
        try:
            info = MongoClient().server_info()
            print("Mongo ready! Server info:\n{}".format(info))
            break
        except:
            print("Waiting for Mongo to be ready...")
            time.sleep(1)


class NodeFactory:
    @staticmethod
    def _reset_db():
        SafeDriver.flush()

    @staticmethod
    def run(signing_key, node_type):
        _wait_for_redis()
        if node_type == MASTERNODE:
            _wait_for_mongo()
            MasterOps.init_master(key=signing_key)
            mn = Masternode(ip=CilantroConf.HOST_IP, name='Masternode', signing_key=signing_key)
        elif node_type == DELEGATE:
            d = Delegate(ip=CilantroConf.HOST_IP, name='Delegate', signing_key=signing_key)
