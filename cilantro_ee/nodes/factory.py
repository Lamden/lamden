from cilantro_ee.nodes.masternode.masternode import Masternode
from cilantro_ee.nodes.delegate.delegate import Delegate
from cilantro_ee.nodes.witness.witness import Witness
from seneca.engine.interpreter.executor import Executor
from cilantro_ee.storage.ledis import SafeLedis
from cilantro_ee.nodes.masternode.master_store import MasterOps


def _wait_for_ledis():
    import ledis, time
    while True:
        try:
            l = ledis.Ledis()
            print("Ledis ready!")
            break
        except:
            print("Waiting for Ledis to be ready...")
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


class NodeFactory:
    @staticmethod
    def _reset_db():
        print("-------\tResetting database\t-------")
        SafeLedis.flushall()

    @staticmethod
    def _seed_if_necessary():
        indicator_key = 'contracts:smart_contract'  # if contracts are seeded, we expect this key to exist
        if not SafeLedis.exists(indicator_key):
            print("No contracts found in db. Seeding contracts")
            interface = Executor(concurrency=False, currency=False)
        else:
            print("Contracts already found in db. Skipping seeding.")

    @staticmethod
    def run_masternode(signing_key, ip, name='Masternode', reset_db=False):
        _wait_for_ledis()
        _wait_for_mongo()
        if reset_db:
            NodeFactory._reset_db()
        NodeFactory._seed_if_necessary()
        MasterOps.init_master(key=signing_key)
        mn = Masternode(ip=ip, name=name, signing_key=signing_key)

    @staticmethod
    def run_witness(signing_key, ip, name='Witness', reset_db=False):
        _wait_for_ledis()
        if reset_db:
            NodeFactory._reset_db()
        NodeFactory._seed_if_necessary()
        w = Witness(ip=ip, name=name, signing_key=signing_key)

    @staticmethod
    def run_delegate(signing_key, ip, name='Delegate', reset_db=False):
        _wait_for_ledis()
        if reset_db:
            NodeFactory._reset_db()
        NodeFactory._seed_if_necessary()
        d = Delegate(ip=ip, name=name, signing_key=signing_key)
