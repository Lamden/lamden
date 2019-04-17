from cilantro_ee.nodes.masternode.masternode import Masternode
from cilantro_ee.nodes.delegate.delegate import Delegate
from cilantro_ee.nodes.witness.witness import Witness
from cilantro_ee.nodes.scheduler.scheduler import Scheduler
from seneca.execution.executor import Executor
from cilantro_ee.storage.contracts import mint_wallets
from cilantro_ee.storage.ledis import SafeLedis
from cilantro_ee.nodes.masternode.master_store import MasterOps
from cilantro_ee.constants.conf import CilantroConf


def _wait_for_ledis():
    import ledis, time
    while True:
        try:
            SafeLedis.ping()
            print("Ledis ready! Pinged")
            break
        except:
            print("Waiting for Ledis to be ready...")
            time.sleep(1)


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
        SafeLedis.flushall()

    @staticmethod
    def _seed_if_necessary():
        # TODO (possibly) update key to reflect changes by Dr. ArbitraryRefactor, software's most notorious supervillain
        indicator_key = 'contracts:smart_contract'  # if contracts are seeded, we expect this key to exist

        # ALSO -- i dont think this works as intended. Something unexpected is occurring in seneca that causes
        # data to be seeded before we explicitly tell it to down below

        if not SafeLedis.exists(indicator_key):
            print("No contracts found in db. Seeding contracts")
            interface = Executor(concurrency=False, metering=False)
            mint_wallets()
        else:
            print("Contracts already found in db. Skipping seeding.")

    @staticmethod
    def run_masternode(signing_key, name='Masternode'):
        _wait_for_ledis()
        _wait_for_mongo()
        if CilantroConf.RESET_DB:
            NodeFactory._reset_db()
        NodeFactory._seed_if_necessary()
        MasterOps.init_master(key=signing_key)
        mn = Masternode(ip=CilantroConf.HOST_IP, name=name, signing_key=signing_key)

    @staticmethod
    def run_witness(signing_key, name='Witness'):
        _wait_for_ledis()
        if CilantroConf.RESET_DB:
            NodeFactory._reset_db()
        NodeFactory._seed_if_necessary()
        w = Witness(ip=CilantroConf.HOST_IP, name=name, signing_key=signing_key)

    @staticmethod
    def run_delegate(signing_key, name='Delegate'):
        _wait_for_ledis()
        if CilantroConf.RESET_DB:
            NodeFactory._reset_db()
        NodeFactory._seed_if_necessary()
        d = Delegate(ip=CilantroConf.HOST_IP, name=name, signing_key=signing_key)

    @staticmethod
    def run_scheduler(signing_key, name='Scheduler'):
        _wait_for_ledis()
        if CilantroConf.RESET_DB:
            NodeFactory._reset_db()
        NodeFactory._seed_if_necessary()
        s = Scheduler(ip=CilantroConf.HOST_IP, name=name, signing_key=signing_key)
