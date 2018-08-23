from cilantro.nodes import Masternode, Witness, Delegate, NodeBase
from cilantro.protocol.reactor.manager import ExecutorManager
from cilantro.protocol.transport import Router, Composer
import asyncio

from cilantro.storage.db import DB


class NodeFactory:

    @staticmethod
    def _build_node(loop, signing_key, ip, node_cls, name) -> NodeBase:

        node = node_cls(signing_key=signing_key, ip=ip, loop=loop, name=name)
        router = Router(get_handler_func=lambda: node.state, name=name)
        manager = ExecutorManager(signing_key=signing_key, router=router, name=node_cls.__name__, loop=loop)
        composer = Composer(manager=manager, signing_key=signing_key, name=name)

        node.composer = composer
        router.composer = composer

        return node

    @staticmethod
    def run_masternode(signing_key, ip, name='Masternode', reset_db=False):
        with DB(should_reset=reset_db) as db:
            pass

        loop = asyncio.new_event_loop()

        mn = NodeFactory._build_node(loop=loop, signing_key=signing_key, ip=ip, node_cls=Masternode, name=name)

        mn.start()

    @staticmethod
    def run_witness(signing_key, ip, name='Witness', reset_db=False):
        with DB(should_reset=reset_db) as db:
            pass
        loop = asyncio.new_event_loop()

        w = NodeFactory._build_node(loop=loop, signing_key=signing_key, ip=ip, node_cls=Witness, name=name)

        w.start()

    @staticmethod
    def run_delegate(signing_key, ip, name='Delegate', reset_db=False):
        with DB(should_reset=reset_db) as db:
            pass

        loop = asyncio.new_event_loop()

        d = NodeFactory._build_node(loop=loop, signing_key=signing_key, ip=ip, node_cls=Delegate, name=name)

        d.start()
