import unittest, time, random, cilantro, asyncio, ujson as json, os
from cilantro.utils.test.mp_test_case import wrap_func
from cilantro.constants.vmnet import get_constitution, get_config_file
from vmnet.cloud.testcase import AWSTestCase

CONSTITUION_JSON = None
# CONSTITUION_JSON = '2-2-2.json'

def masternode(idx):
    from cilantro.logger import get_logger
    log = get_logger('MasterNode_{}'.format(idx))

    from cilantro.protocol.overlay.discovery import Discovery
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os, ujson as json, sys
    from cilantro.storage.vkbook import VKBook
    VKBook.setup(CONSTITUION_JSON)

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Discovery.discovered_nodes) >= 1:
                quit()

    loop = asyncio.get_event_loop()
    Auth.setup(VKBook.constitution['masternodes'][idx]['sk'])
    Discovery.setup()
    tasks = asyncio.ensure_future(asyncio.gather(
        Discovery.listen(),
        Discovery.discover_nodes(os.getenv('HOST_IP')),
        check_nodes()
    ))
    loop.run_until_complete(tasks)


def delegates(idx):
    from cilantro.logger import get_logger
    log = get_logger('DelegateNode_{}'.format(idx))
    from cilantro.protocol.overlay.discovery import Discovery
    from cilantro.protocol.overlay.auth import Auth
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    import asyncio, os, ujson as json, sys
    from cilantro.storage.vkbook import VKBook
    VKBook.setup(CONSTITUION_JSON)

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Discovery.discovered_nodes) >= MIN_BOOTSTRAP_NODES:
                quit()

    loop = asyncio.get_event_loop()
    Auth.setup(VKBook.constitution['delegates'][idx]['sk'])
    Discovery.setup()
    tasks = asyncio.ensure_future(asyncio.gather(
        Discovery.listen(),
        Discovery.discover_nodes(os.getenv('HOST_IP')),
        check_nodes()
    ))
    loop.run_until_complete(tasks)

class TestCloud(AWSTestCase):

    config_file = get_config_file('cilantro_aws.json')
    keep_up = False
    timeout = 120

    def test_aws(self):
        for idx, node in enumerate(self.groups['masternode']):
            self.execute_python(node, wrap_func(masternode, idx))
        for idx, node in enumerate(self.groups['delegate']):
            self.execute_python(node, wrap_func(delegates, idx))

if __name__ == '__main__':
    unittest.main()
