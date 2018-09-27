from cilantro.nodes.masternode.masternode import Masternode
from cilantro.nodes.delegate.delegate import Delegate
from cilantro.nodes.witness.witness import Witness
from cilantro.storage.db import DB


class NodeFactory:

    @staticmethod
    def run_masternode(signing_key, ip, name='Masternode', reset_db=False):
        with DB(should_reset=reset_db) as db:
            pass

        mn = Masternode(ip=ip, name=name, signing_key=signing_key)

    @staticmethod
    def run_witness(signing_key, ip, name='Witness', reset_db=False):
        with DB(should_reset=reset_db) as db:
            pass

        w = Witness(ip=ip, name=name, signing_key=signing_key)

    @staticmethod
    def run_delegate(signing_key, ip, name='Delegate', reset_db=False):
        with DB(should_reset=reset_db) as db:
            pass

        d = Delegate(ip=ip, name=name, signing_key=signing_key)

