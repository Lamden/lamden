from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger

def masternode(idx, node_count):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
    from cilantro.protocol.overlay.handshake import Handshake
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Handshake.authorized_nodes['*']) == node_count:
                send_to_file(os.getenv('HOST_NAME'))

    async def send_handshake():
        await asyncio.sleep(5)
        await asyncio.gather(
            *[Handshake.initiate_handshake(node['ip'], vk=node['vk']) \
                for node in all_nodes])

    from cilantro.logger import get_logger
    log = get_logger('MasterNode_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Handshake.setup()
    Auth.setup_certs_dirs(TESTNET_MASTERNODES[idx]['sk'])
    masternodes = [{'vk': node['vk'], 'ip': os.getenv('MASTERNODE').split(',')[idx]} for idx, node in enumerate(TESTNET_MASTERNODES)]
    witnesses = [{'vk': node['vk'], 'ip': os.getenv('WITNESS').split(',')[idx]} for idx, node in enumerate(TESTNET_WITNESSES)]
    delegates = [{'vk': node['vk'], 'ip': os.getenv('DELEGATE').split(',')[idx]} for idx, node in enumerate(TESTNET_DELEGATES)]
    all_nodes = masternodes + witnesses + delegates
    tasks = asyncio.ensure_future(asyncio.gather(
        send_handshake(),
        Handshake.listen(),
        check_nodes()
    ))
    loop.run_until_complete(tasks)

def witness(idx, node_count):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
    from cilantro.protocol.overlay.handshake import Handshake
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Handshake.authorized_nodes['*']) == node_count:
                send_to_file(os.getenv('HOST_NAME'))

    async def send_handshake():
        await asyncio.sleep(5)
        await asyncio.gather(
            *[Handshake.initiate_handshake(node['ip'], vk=node['vk']) \
                for node in all_nodes])

    from cilantro.logger import get_logger
    log = get_logger('Witness_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Handshake.setup()
    Auth.setup_certs_dirs(TESTNET_WITNESSES[idx]['sk'])
    masternodes = [{'vk': node['vk'], 'ip': os.getenv('MASTERNODE').split(',')[idx]} for idx, node in enumerate(TESTNET_MASTERNODES)]
    witnesses = [{'vk': node['vk'], 'ip': os.getenv('WITNESS').split(',')[idx]} for idx, node in enumerate(TESTNET_WITNESSES)]
    delegates = [{'vk': node['vk'], 'ip': os.getenv('DELEGATE').split(',')[idx]} for idx, node in enumerate(TESTNET_DELEGATES)]
    all_nodes = masternodes + witnesses + delegates
    tasks = asyncio.ensure_future(asyncio.gather(
        send_handshake(),
        Handshake.listen(),
        check_nodes()
    ))
    loop.run_until_complete(tasks)

def delegate(idx, node_count):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
    from cilantro.protocol.overlay.handshake import Handshake
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Handshake.authorized_nodes['*']) == node_count:
                send_to_file(os.getenv('HOST_NAME'))

    async def send_handshake():
        await asyncio.sleep(5)
        await asyncio.gather(
            *[Handshake.initiate_handshake(node['ip'], vk=node['vk']) \
                for node in all_nodes])

    from cilantro.logger import get_logger
    log = get_logger('Delegate_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Handshake.setup()
    Auth.setup_certs_dirs(TESTNET_DELEGATES[idx]['sk'])
    masternodes = [{'vk': node['vk'], 'ip': os.getenv('MASTERNODE').split(',')[idx]} for idx, node in enumerate(TESTNET_MASTERNODES)]
    witnesses = [{'vk': node['vk'], 'ip': os.getenv('WITNESS').split(',')[idx]} for idx, node in enumerate(TESTNET_WITNESSES)]
    delegates = [{'vk': node['vk'], 'ip': os.getenv('DELEGATE').split(',')[idx]} for idx, node in enumerate(TESTNET_DELEGATES)]
    all_nodes = masternodes + witnesses + delegates
    tasks = asyncio.ensure_future(asyncio.gather(
        send_handshake(),
        Handshake.listen(),
        check_nodes()
    ))
    loop.run_until_complete(tasks)

class TestHandshake(BaseTestCase):

    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-2-2-4-bootstrap.json')

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)

    def complete(self):
        all_nodes = set(self.groups['masternode']+self.groups['witness']+self.groups['delegate'])
        self.assertEqual(self.nodes_complete, all_nodes)

    def test_dump(self):
        self.nodes_complete = set()
        node_count = len(self.groups['masternode']+self.groups['witness']+self.groups['delegate'])
        for idx, node in enumerate(self.groups['masternode']):
            self.execute_python(node, wrap_func(masternode, idx, node_count))
        for idx, node in enumerate(self.groups['witness']):
            self.execute_python(node, wrap_func(witness, idx, node_count))
        for idx, node in enumerate(self.groups['delegate']):
            self.execute_python(node, wrap_func(delegate, idx, node_count))

        file_listener(self, self.callback, self.complete, 20)

if __name__ == '__main__':
    unittest.main()
