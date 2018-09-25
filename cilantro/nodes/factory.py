from cilantro.nodes.base import NodeBase, NewNodeBase
from cilantro.nodes.masternode.masternode import Masternode
from cilantro.nodes.delegate.delegate import Delegate
from cilantro.nodes.witness.witness import Witness
from cilantro.protocol.executors.manager import ExecutorManager
from cilantro.protocol.transport import Router, Composer

import asyncio
import zmq.asyncio

from cilantro.storage.db import DB


class NodeFactory:

    @staticmethod
    def _build_node(loop, signing_key, ip, node_cls, name) -> NodeBase:

        asyncio.set_event_loop(loop)
        ctx = zmq.asyncio.Context()

        node = node_cls(signing_key=signing_key, ip=ip, loop=loop, name=name)
        router = Router(get_handler_func=lambda: node.state, name=name)
        manager = ExecutorManager(signing_key=signing_key, context=ctx, router=router, name=node_cls.__name__, loop=loop)
        composer = Composer(manager=manager, signing_key=signing_key, ip=ip, name=name)

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

        w = Witness(ip=ip, name=name, signing_key=signing_key)

    @staticmethod
    def run_delegate(signing_key, ip, name='Delegate', reset_db=False):
        with DB(should_reset=reset_db) as db:
            pass

        loop = asyncio.new_event_loop()

        d = NodeFactory._build_node(loop=loop, signing_key=signing_key, ip=ip, node_cls=Delegate, name=name)

        d.start()
