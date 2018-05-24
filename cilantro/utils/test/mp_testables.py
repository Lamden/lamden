from cilantro import Constants
from cilantro.utils.test import MPTesterBase, mp_testable, God
from unittest.mock import patch, call, MagicMock
from cilantro.protocol.transport import Router, Composer
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.statemachine import StateMachine
from cilantro.nodes import Masternode, Delegate, Witness, NodeFactory
import asyncio


@mp_testable(Composer)
class MPComposer(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, name='') -> tuple:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mock_sm = MagicMock(spec=StateMachine)
        mock_sm.__name__ = name
        router = MagicMock()

        reactor = ReactorInterface(router=router, loop=loop, verifying_key=Constants.Protocol.Wallets.get_vk(sk))
        composer = Composer(interface=reactor, signing_key=sk)

        return composer, loop, [reactor._recv_messages()]


@mp_testable(God)
class MPGod(MPTesterBase):
    @classmethod
    def build_obj(cls) -> tuple:
        loop = asyncio.new_event_loop()
        god = God(loop=loop)

        return god, loop, [god.interface._recv_messages()]


@mp_testable(Masternode)
class MPMasternode(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, url, name='Masternode') -> tuple:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        mn = NodeFactory._build_node(loop=loop, signing_key=sk, ip=url, node_cls=Masternode, name=name)
        mn.start(start_loop=False)

        tasks = mn.tasks + [mn.composer.interface._recv_messages()]

        return mn, loop, tasks


@mp_testable(Witness)
class MPWitness(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, url, name='Masternode') -> tuple:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        witness = NodeFactory._build_node(loop=loop, signing_key=sk, ip=url, node_cls=Witness, name=name)
        witness.start(start_loop=False)

        tasks = witness.tasks + [witness.composer.interface._recv_messages()]

        return witness, loop, tasks
