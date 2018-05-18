from vmnet.test.base import *
from vmnet.test.util import *
import unittest, time, random

def run_pub():
    from cilantro.nodes.utilitynodes import PubNode
    import time, asyncio
    p = PubNode()
    time.sleep(5)
    future = asyncio.ensure_future(p.debug_forever_pub())
    p.loop.run_forever()

def run_sub():
    from cilantro.nodes.utilitynodes import SubNode
    s = SubNode('172.29.5.1')
    s.loop.run_forever()

class TestReactorNodes(BaseNetworkTestCase):
    testname = 'reactor_nodes'
    setuptime = 10
    compose_file = 'cilantro-nodes.yml'
    def test_basic_pub_sub(self):
        self.execute_python('node_1', run_pub, async=True)
        time.sleep(2)
        for i in range(2,9):
            self.execute_python('node_{}'.format(i), run_sub, async=True)
        time.sleep(360)

if __name__ == '__main__':
    unittest.main()
