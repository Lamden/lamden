from cilantro.logger import get_logger
from cilantro.utils.test.mp_test_case import MPTestCase
from cilantro.utils.test.mp_test import MPTesterBase, mp_testable
from cilantro.utils.test.god import God
from unittest.mock import MagicMock
from cilantro.protocol.transport.composer import Composer
from cilantro.protocol.executors.manager import ExecutorManager
from cilantro.protocol.states.statemachine import StateMachine
from cilantro.nodes.masternode.masternode import Masternode
from cilantro.nodes.delegate.delegate import Delegate
from cilantro.nodes.witness.witness import Witness
from cilantro.nodes.base import NodeBase
from cilantro.protocol.overlay.server import OverlayServer
from cilantro.utils.lprocess import LProcess
# from cilantro.storage.db import DB
from cilantro.utils.test.pubsub_auth import PubSubAuthTester
from cilantro.utils.test.router_auth import RouterAuthTester
import asyncio
import zmq.asyncio
import os
from cilantro.storage.vkbook import VKBook


@mp_testable(NodeBase)
class MPNodeBase(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, name='Node'):
        VKBook.setup()
        ip = os.getenv('HOST_IP', '127.0.0.1')
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)
        obj = NodeBase(ip=ip, signing_key=sk, loop=loop, name=name)

        return obj, loop, []


@mp_testable(PubSubAuthTester)
class MPPubSubAuth(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, name='') -> tuple:
        VKBook.setup()
        # # DEBUG -- TODO DELETE
        # print("VKBook on REMOTE MACHINE")
        # from cilantro.storage.vkbook import VKBook
        # VKBook.test_print_nodes()
        # # END DEBUG
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)

        # Start Overlay Process
        overlay_proc = LProcess(target=OverlayServer, args=(sk,))
        overlay_proc.start()

        obj = PubSubAuthTester(sk, name=name, loop=loop)

        return obj, loop, []


@mp_testable(RouterAuthTester)
class MPRouterAuth(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, name='') -> tuple:
        VKBook.setup()
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)

        # Start Overlay Process
        overlay_proc = LProcess(target=OverlayServer, args=(sk,))
        overlay_proc.start()

        obj = RouterAuthTester(sk, name=name, loop=loop)

        return obj, loop, []


@mp_testable(Composer)
class MPComposer(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, name='') -> tuple:
        VKBook.setup()
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)
        ctx = zmq.asyncio.Context()

        # Start Overlay Process
        overlay_proc = LProcess(target=OverlayServer, args=(sk,))
        overlay_proc.start()

        router = MagicMock()
        ip = os.getenv('HOST_IP', '127.0.0.1')
        manager = ExecutorManager(signing_key=sk, router=router, name=name, loop=loop, context=ctx)
        composer = Composer(manager=manager, signing_key=sk, ip=ip, name=name)

        return composer, loop, []


@mp_testable(StateMachine)
class MPStateMachine(MPTesterBase):
    @classmethod
    def build_obj(cls, sm_class, name=''):
        VKBook.setup()
        # These 2 lines are probs unnecessary
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)

        sm = sm_class()
        assert isinstance(sm, StateMachine), "Class {} did not return a StateMachine instance once called".format(sm_class)

        # NOTE -- the testing framework should start the loop, so we shouldn't have to worry bout that here
        return sm, loop, []


@mp_testable(God)
class MPGod(MPTesterBase):
    @classmethod
    def build_obj(cls) -> tuple:
        VKBook.setup()
        loop = asyncio.get_event_loop()
        god = God(loop=loop)

        return god, loop, [god.interface._recv_messages()]


# def _build_node(signing_key, name='', node_cls=None) -> tuple:
#     assert node_cls and name, "This is an abstract class. Subclasses must pass in node_cls and name."
#     assert node_cls in (Witness, Masternode, Delegate), "node_cls must be Witness/Masternode/Delegate, not {}".format(node_cls)
#
#     loop = asyncio.get_event_loop()
#     asyncio.set_event_loop(loop)
#
#     with DB(should_reset=True) as db:
#         pass
#
#     ip = os.getenv('HOST_IP', '127.0.0.1')
#
#     node = NodeFactory._build_node(loop=loop, signing_key=signing_key, ip=ip, node_cls=node_cls, name=name)
#     node.start(start_loop=False)
#
#     tasks = node.tasks + [node.composer.interface._recv_messages()]
#
#     return node, loop, tasks
#
#
# @mp_testable(Masternode)
# class MPMasternode(MPTesterBase):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#
#         # Set God's Masternode URL to use this guy updated port if we are running on VM
#         if MPTestCase.vmnet_test_active:
#             node_ports = MPTestCase.ports[self.container_name]
#             assert '8080' in node_ports, "Expected port 8080 to be available in Falcon's docker external port thing"
#             God.set_mn_url(ip='127.0.0.1', port=node_ports['8080'].split(':')[-1])
#
#     @classmethod
#     def build_obj(cls, signing_key, name='Masternode') -> tuple:
#         return _build_node(signing_key=signing_key, name=name, node_cls=Masternode)
#
#
# @mp_testable(Witness)
# class MPWitness(MPTesterBase):
#     @classmethod
#     def build_obj(cls, signing_key, name='Witness') -> tuple:
#         return _build_node(signing_key=signing_key, name=name, node_cls=Witness)
#
#
# @mp_testable(Delegate)
# class MPDelegate(MPTesterBase):
#     @classmethod
#     def build_obj(cls, signing_key, name='Delegate') -> tuple:
#         return _build_node(signing_key=signing_key, name=name, node_cls=Delegate)
