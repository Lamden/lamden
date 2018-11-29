from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES

def masternode(idx, node_count, all_vks):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    from cilantro.protocol.overlay.handshake import Handshake
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os, time

    async def check_nodes():
        while True:
            await asyncio.sleep(3)
            if len(Handshake.authorized_nodes['*']) == node_count:
                send_to_file(os.getenv('HOST_NAME'))

    async def send_handshake():
        await asyncio.sleep(8)
        await asyncio.gather(
            *[Handshake.initiate_handshake(node['ip'], vk=node['vk']) \
                for node in all_nodes])

    from cilantro.logger import get_logger
    log = get_logger('MasterNode_{}'.format(idx))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    Auth.setup(TESTNET_MASTERNODES[idx]['sk'])
    Handshake.setup(loop=loop)

    all_nodes = [{'vk': vk, 'ip': os.getenv('NODE').split(',')[idx]} for idx, vk in enumerate(all_vks)]
    tasks = asyncio.gather(
        send_handshake(),
        Handshake.listen(),
        check_nodes()
    )
    loop.run_until_complete(tasks)

def delegates(idx, node_count, all_vks):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_DELEGATES
    from cilantro.protocol.overlay.handshake import Handshake
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os, time

    async def check_nodes():
        while True:
            await asyncio.sleep(3)
            if len(Handshake.authorized_nodes['*']) == node_count:
                send_to_file(os.getenv('HOST_NAME'))

    async def send_handshake():
        await asyncio.sleep(8)
        await asyncio.gather(
            *[Handshake.initiate_handshake(node['ip'], vk=node['vk']) \
                for node in all_nodes])

    from cilantro.logger import get_logger
    log = get_logger('Delegate_{}'.format(idx))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    Auth.setup(TESTNET_DELEGATES[idx]['sk'])
    Handshake.setup(loop=loop)

    all_nodes = [{'vk': vk, 'ip': os.getenv('NODE').split(',')[idx]} for idx, vk in enumerate(all_vks)]

    tasks = asyncio.gather(
        send_handshake(),
        Handshake.listen(),
        check_nodes()
    )
    loop.run_until_complete(tasks)
    log.critical('I shall not see this')

class TestHandshake(BaseTestCase):

    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-4.json')
    enable_ui = False

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)
        if self.nodes_complete == self.all_nodes:
            self.end_test()

    def timeout(self):
        self.assertEqual(self.nodes_complete, self.all_nodes)

    def test_dump(self):
        self.all_nodes = set(self.groups['node'])
        node_count = len(self.groups['node'])
        self.nodes_complete = set()
        all_vks = [TESTNET_MASTERNODES[0]['vk']] + [n['vk'] for n in TESTNET_DELEGATES[:3]]
        self.execute_python(self.groups['node'][0], wrap_func(masternode, 0, node_count, all_vks))
        for idx, node in enumerate(self.groups['node'][1:]):
            self.execute_python(node, wrap_func(delegates, idx, node_count, all_vks))

        file_listener(self, self.callback, self.timeout, 30)

if __name__ == '__main__':
    unittest.main()
