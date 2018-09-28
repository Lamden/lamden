from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, vmnet, cilantro
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger

def masternode(idx):
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
    from cilantro.protocol.overlay.handshake import Handshake
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os
    from cilantro.logger import get_logger
    log = get_logger('MasterNode_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Auth.setup_certs_dirs(TESTNET_MASTERNODES[idx]['sk'])
    masternodes = [{'vk': node['vk'], 'ip': os.getenv('MASTERNODE').split(',')[idx]} for idx, node in enumerate(TESTNET_MASTERNODES)]
    witnesses = [{'vk': node['vk'], 'ip': os.getenv('WITNESS').split(',')[idx]} for idx, node in enumerate(TESTNET_WITNESSES)]
    delegates = [{'vk': node['vk'], 'ip': os.getenv('DELEGATE').split(',')[idx]} for idx, node in enumerate(TESTNET_DELEGATES)]
    all_nodes = masternodes + witnesses + delegates
    tasks = asyncio.ensure_future(asyncio.gather(
        *[Handshake.initiate_handshake(node['ip'], vk=node['vk']) \
            for node in all_nodes],
        Handshake.listen_for_handshake()
    ))
    loop.run_until_complete(tasks)

def witness(idx):
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
    from cilantro.protocol.overlay.handshake import Handshake
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os
    from cilantro.logger import get_logger
    log = get_logger('Witness_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Auth.setup_certs_dirs(TESTNET_WITNESSES[idx]['sk'])
    masternodes = [{'vk': node['vk'], 'ip': os.getenv('MASTERNODE').split(',')[idx]} for idx, node in enumerate(TESTNET_MASTERNODES)]
    witnesses = [{'vk': node['vk'], 'ip': os.getenv('WITNESS').split(',')[idx]} for idx, node in enumerate(TESTNET_WITNESSES)]
    delegates = [{'vk': node['vk'], 'ip': os.getenv('DELEGATE').split(',')[idx]} for idx, node in enumerate(TESTNET_DELEGATES)]
    all_nodes = masternodes + witnesses + delegates
    tasks = asyncio.ensure_future(asyncio.gather(
        *[Handshake.initiate_handshake(node['ip'], vk=node['vk']) \
            for node in all_nodes],
        Handshake.listen_for_handshake()
    ))
    loop.run_until_complete(tasks)

def delegate(idx):
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
    from cilantro.protocol.overlay.handshake import Handshake
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os
    from cilantro.logger import get_logger
    log = get_logger('Delegate_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Auth.setup_certs_dirs(TESTNET_DELEGATES[idx]['sk'])
    masternodes = [{'vk': node['vk'], 'ip': os.getenv('MASTERNODE').split(',')[idx]} for idx, node in enumerate(TESTNET_MASTERNODES)]
    witnesses = [{'vk': node['vk'], 'ip': os.getenv('WITNESS').split(',')[idx]} for idx, node in enumerate(TESTNET_WITNESSES)]
    delegates = [{'vk': node['vk'], 'ip': os.getenv('DELEGATE').split(',')[idx]} for idx, node in enumerate(TESTNET_DELEGATES)]
    all_nodes = masternodes + witnesses + delegates
    tasks = asyncio.ensure_future(asyncio.gather(
        *[Handshake.initiate_handshake(node['ip'], vk=node['vk']) \
            for node in all_nodes],
        Handshake.listen_for_handshake()
    ))
    loop.run_until_complete(tasks)

class TestHandshake(BaseNetworkTestCase):

    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-2-4-4-bootstrap.json')

    @vmnet_test(run_webui=True)
    def test_dump(self):
        for idx, node in enumerate(self.groups['masternode']):
            self.execute_python(node, wrap_func(masternode, idx))
        for idx, node in enumerate(self.groups['witness']):
            self.execute_python(node, wrap_func(witness, idx))
        for idx, node in enumerate(self.groups['delegate']):
            self.execute_python(node, wrap_func(delegate, idx))

        input("Press any key to terminate")

if __name__ == '__main__':
    unittest.main()
