from cilantro import Constants
from cilantro.nodes import Masternode, Witness, Delegate
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.transport import Router, Composer
import asyncio
from unittest.mock import MagicMock



W = Constants.Protocol.Wallets


class NodeFactory:
    @staticmethod
    def build_mock_node(signing_key: str, loop):
        sm = MagicMock()
        router = Router(statemachine=sm)
        interface = ReactorInterface(router=router, loop=loop)
        composer = Composer(interface=interface, signing_key=signing_key, sender_id=W.get_vk(signing_key))

        # irl we would just set composer, but for testing purposes we setting them all
        sm.composer = composer
        sm.router = router
        sm.interface = interface

        return sm

    @staticmethod
    def run_mock_node(signing_key: str):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        node = NodeFactory.build_mock_node(signing_key=signing_key, loop=loop)

        loop.run_forever()

    @staticmethod
    def build_masternode(loop, signing_key=Constants.Testnet.Masternode.Sk, url=Constants.Testnet.Masternode.InternalUrl):
        mn = Masternode(signing_key=signing_key, url=url)
        router = Router(statemachine=mn)
        interface = ReactorInterface(router=router, loop=loop)
        composer = Composer(interface=interface, signing_key=signing_key, sender_id=W.get_vk(signing_key))

        # irl we would just set composer, but for testing purposes we setting them all
        mn.composer = composer
        mn.router = router
        mn.interface = interface

        return mn

    @staticmethod
    def run_masternode(signing_key=Constants.Testnet.Masternode.Sk, url=Constants.Testnet.Masternode.InternalUrl):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mn = NodeFactory.build_masternode(loop=loop, signing_key=signing_key, url=url)

        loop.run_forever()

