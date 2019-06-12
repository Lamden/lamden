from cilantro_ee.nodes.masternode.masternode import Masternode
from cilantro_ee.nodes.delegate.delegate import Delegate
from cilantro_ee.nodes.witness.witness import Witness
from cilantro_ee.nodes.scheduler.scheduler import Scheduler
from cilantro_ee.storage.contracts import mint_wallets
from cilantro_ee.storage.driver import SafeDriver
from cilantro_ee.nodes.masternode.master_store import MasterOps
from cilantro_ee.constants.conf import CilantroConf


def _wait_for_redis():
    # import ledis, time
    import time

    # TODO implement reactive solution
    time.sleep(20)

    # while True:
    #     try:
    #         SafeDriver.ping()
    #         print("Ledis ready! Pinged")
    #         break
    #     except:
    #         print("Waiting for Ledis to be ready...")
    #         time.sleep(1)


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
        print("-------\tResetting database\t-------")

        # TODO make this a database agnostic command
        SafeDriver.flush()

    @staticmethod
    def run_masternode(signing_key, name='Masternode'):
        _wait_for_redis()
        _wait_for_mongo()
        MasterOps.init_master(key=signing_key)
        mn = Masternode(ip=CilantroConf.HOST_IP, name=name, signing_key=signing_key)

    @staticmethod
    def run_witness(signing_key, name='Witness'):
        _wait_for_redis()
        w = Witness(ip=CilantroConf.HOST_IP, name=name, signing_key=signing_key)

    @staticmethod
    def run_delegate(signing_key, name='Delegate'):
        _wait_for_redis()
        d = Delegate(ip=CilantroConf.HOST_IP, name=name, signing_key=signing_key)

    @staticmethod
    def run_scheduler(signing_key, name='Scheduler'):
        _wait_for_redis()
        s = Scheduler(ip=CilantroConf.HOST_IP, name=name, signing_key=signing_key)
