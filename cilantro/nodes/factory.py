from cilantro.nodes import Masternode, Witness, Delegate, NodeBase
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.transport import Router, Composer
import asyncio
from unittest.mock import MagicMock
from cilantro.protocol.wallet import Wallet


W = Wallet


class NodeFactory:

    @staticmethod
    def _build_node(loop, signing_key, ip, node_cls, name) -> NodeBase:

        node = node_cls(signing_key=signing_key, ip=ip, loop=loop, name=name)
        router = Router(statemachine=node, name=name)
        interface = ReactorInterface(router=router, loop=loop, signing_key=signing_key, name=name)
        composer = Composer(interface=interface, signing_key=signing_key, name=name)

        node.composer = composer

        return node

    @staticmethod
    def run_masternode(signing_key, ip, name='Masternode'):
        loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)

        mn = NodeFactory._build_node(loop=loop, signing_key=signing_key, ip=ip, node_cls=Masternode, name=name)

        mn.start()

    @staticmethod
    def run_witness(signing_key, ip, name='Witness'):
        loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)

        w = NodeFactory._build_node(loop=loop, signing_key=signing_key, ip=ip, node_cls=Witness, name=name)

        w.start()

    @staticmethod
    def run_delegate(signing_key, ip, name='Delegate'):
        loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)

        d = NodeFactory._build_node(loop=loop, signing_key=signing_key, ip=ip, node_cls=Delegate, name=name)

        d.start()
