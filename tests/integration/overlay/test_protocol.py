from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro, asyncio, ujson as json
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger

def node(idx):
    import os
    from cilantro.protocol.overlay.kademlia import KademliaProtocol
    from cilantro.protocol.overlay.kademlia import Network
    from cilantro.logger.base import get_logger

    log = get_logger('Node_{}'.format(idx))

    neighbors = (os.getenv('NODE').split(',') * 2)[idx:idx+3]

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    network = Network(loop=loop)
    network.listen()

class TestProtocol(BaseTestCase):

    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-8.json')
    enable_ui = True

    def test_protocol(self):
        for idx, node in enumerate(self.groups['node']):
            self.execute_python(node, wrap_func(node, idx))

if __name__ == '__main__':
    unittest.main()
