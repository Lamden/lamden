from cilantro.logger import get_logger
from cilantro.utils.test import MPTesterBase, mp_testable, God, MPTestCase
from unittest.mock import MagicMock
from cilantro.protocol.transport import Composer
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.states.statemachine import StateMachine
from cilantro.nodes import Masternode, Witness, Delegate, NodeFactory
from cilantro.storage.db import DB
import asyncio
import os


def _build_node(signing_key, name='', node_cls=None) -> tuple:
    assert node_cls and name, "This is an abstract class. Subclasses must pass in node_cls and name."
    assert node_cls in (Witness, Masternode, Delegate), "node_cls must be Witness/Masternode/Delegate, not {}".format(node_cls)

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    with DB(should_reset=True) as db:
        pass

    ip = os.getenv('HOST_IP', '127.0.0.1')

    node = NodeFactory._build_node(loop=loop, signing_key=signing_key, ip=ip, node_cls=node_cls, name=name)
    node.start(start_loop=False)
    
    tasks = node.tasks + [node.composer.interface._recv_messages()]

    return node, loop, tasks


@mp_testable(Composer)
class MPComposer(MPTesterBase):
    @classmethod
    def build_obj(cls, sk, name='') -> tuple:
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)

        mock_sm = MagicMock(spec=StateMachine)
        mock_sm.__name__ = name
        router = MagicMock()

        reactor = ReactorInterface(router=router, loop=loop, signing_key=sk)
        composer = Composer(manager=reactor, signing_key=sk)

        return composer, loop, [reactor._recv_messages()]


@mp_testable(StateMachine)
class MPStateMachine(MPTesterBase):
    @classmethod
    def build_obj(cls, sm_class):
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
        loop = asyncio.get_event_loop()
        god = God(loop=loop)

        return god, loop, [god.interface._recv_messages()]


@mp_testable(Masternode)
class MPMasternode(MPTesterBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set God's Masternode URL to use this guy updated port if we are running on VM
        if MPTestCase.vmnet_test_active:
            node_ports = MPTestCase.ports[self.container_name]
            assert '8080' in node_ports, "Expected port 8080 to be available in Falcon's docker external port thing"
            God.set_mn_url(ip='127.0.0.1', port=node_ports['8080'].split(':')[-1])

    @classmethod
    def build_obj(cls, signing_key, name='Masternode') -> tuple:
        return _build_node(signing_key=signing_key, name=name, node_cls=Masternode)


@mp_testable(Witness)
class MPWitness(MPTesterBase):
    @classmethod
    def build_obj(cls, signing_key, name='Witness') -> tuple:
        return _build_node(signing_key=signing_key, name=name, node_cls=Witness)


@mp_testable(Delegate)
class MPDelegate(MPTesterBase):
    @classmethod
    def build_obj(cls, signing_key, name='Delegate') -> tuple:
        return _build_node(signing_key=signing_key, name=name, node_cls=Delegate)

