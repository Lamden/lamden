from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro, asyncio, ujson as json
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger

def nodefn(idx):

    import os, asyncio
    from cilantro.protocol.overlay.kademlia.crawling import NodeSpiderCrawl
    from cilantro.protocol.overlay.kademlia.network import Network
    from cilantro.constants.ports import DHT_PORT
    from cilantro.protocol.overlay.kademlia.node import Node
    from cilantro.protocol.overlay.kademlia.utils import digest
    from cilantro.protocol.overlay.auth import Auth
    from cilantro.logger.base import get_logger
    from vmnet.comm import send_to_file

    log = get_logger('Node_{}'.format(idx+1))

    sourceNode = Node(
        digest(os.getenv('HOST_IP')),
        ip=os.getenv('HOST_IP'),
        port=DHT_PORT
    )
    neighbors = (os.getenv('NODE').split(',') * 2)[idx+1:idx+4]

    async def bootstrap_nodes(ipsToAsk):
        await network.bootstrap([(ip, DHT_PORT) for ip in ipsToAsk])

    async def find_neighbors(ipsToAsk, ipToFind):
        await asyncio.sleep(3)
        nodesToAsk = [
            Node(
                digest(ip),
                ip=ip,
                port=DHT_PORT
            ) for ip in ipsToAsk
        ]
        nodeToFind = Node(
            digest(ipToFind),
            ip=ipToFind,
            port=DHT_PORT
        )

        spider = NodeSpiderCrawl(network.protocol, nodeToFind, nodesToAsk, 3, 3)
        res = await spider.find()
        res = [r.ip for r in res]
        log.critical(res)
        if ipToFind in res:
            send_to_file(os.getenv('HOST_NAME'))
            log.important('Found {}!'.format(ipToFind))
        else:
            log.fatal('Failed to find {}!'.format(ipToFind))

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    network = Network()
    network.node.id = digest(os.getenv('HOST_IP')) ### Mock only

    loop.run_until_complete(asyncio.gather(
        *network.tasks,
        bootstrap_nodes(neighbors[:-1]),
        find_neighbors(set(neighbors[:-1]), neighbors[-1])
    ))

class TestProtocol(BaseTestCase):

    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-8.json')
    enable_ui = True

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)
        if self.nodes_complete == self.all_nodes:
            self.end_test()

    def timeout(self):
        self.assertEqual(self.nodes_complete, self.all_nodes)

    def test_protocol(self):
        self.all_nodes = set(self.groups['node'])
        self.nodes_complete = set()
        for idx, node in enumerate(self.groups['node']):
            self.execute_python(node, wrap_func(nodefn, idx))

        file_listener(self, self.callback, self.timeout, 30)

if __name__ == '__main__':
    unittest.main()
