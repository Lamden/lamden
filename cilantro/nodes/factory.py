from cilantro import Constants
from cilantro.nodes import Masternode, Witness, Delegate, NodeBase
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.transport import Router, Composer
import asyncio
from unittest.mock import MagicMock



W = Constants.Protocol.Wallets


class NodeFactory:

    @staticmethod
    def _build_node(loop, signing_key, url, node_cls) -> NodeBase:
        node = node_cls(signing_key=signing_key, url=url, loop=loop)
        router = Router(statemachine=node)
        interface = ReactorInterface(router=router, loop=loop)
        composer = Composer(interface=interface, signing_key=signing_key)

        node.composer = composer

        return node


    @staticmethod
    def run_masternode(signing_key=Constants.Testnet.Masternode.Sk, url=Constants.Testnet.Masternode.InternalUrl):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mn = NodeFactory._build_node(loop=loop, signing_key=signing_key, url=url, node_cls=Masternode)

        mn.start()

    @staticmethod
    def run_witness(signing_key='51066195e63be3c8d5c14d3c1561b90a1f0f0789b5c2b44254a4a211edac1ec6',
                    url='tcp://127.0.0.1:6000'):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        w = NodeFactory._build_node(loop=loop, signing_key=signing_key, url=url, node_cls=Witness)

        w.start()

    @staticmethod
    def run_delegate(signing_key, url):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        d = NodeFactory._build_node(loop=loop, signing_key=signing_key, url=url, node_cls=Delegate)

        d.start()
