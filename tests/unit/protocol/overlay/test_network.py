from unittest import TestCase
import asyncio
from cilantro_ee.protocol.overlay.kademlia.discovery import *
from cilantro_ee.protocol.overlay.kademlia.new_network import Network
from cilantro_ee.constants.overlay_network import PEPPER
import zmq
import zmq.asyncio
from cilantro_ee.protocol.wallet import Wallet
from time import sleep

TIME_UNIT = 0.01


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


def run_silent_loop(tasks, s=TIME_UNIT):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(tasks)
    except RuntimeError as e:
        pass
    sleep(s)


async def timeout_bomb(s=TIME_UNIT*2):
    await asyncio.sleep(s)
    asyncio.get_event_loop().close()


class TestNetworkService(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_setup(self):
        w = Wallet()
        Network(wallet=w, ctx=self.ctx)

    def test_bootstrap_nodes(self):
        w = Wallet()

        w1 = Wallet()
        w2 = Wallet()
        w3 = Wallet()
        w4 = Wallet()

        d1 = DiscoveryServer('inproc://testing1', w1, PEPPER.encode(), ctx=self.ctx)
        d2 = DiscoveryServer('inproc://testing2', w2, PEPPER.encode(), ctx=self.ctx)
        d3 = DiscoveryServer('inproc://testing3', w3, PEPPER.encode(), ctx=self.ctx)
        d4 = DiscoveryServer('inproc://testing4', w4, PEPPER.encode(), ctx=self.ctx)

        bootnodes = ['inproc://testing1', 'inproc://testing2', 'inproc://testing3', 'inproc://testing4']

        n = Network(wallet=w, ctx=self.ctx, bootnodes=bootnodes)

        tasks = asyncio.gather(
            d1.serve(),
            d2.serve(),
            d3.serve(),
            d4.serve(),
            stop_server(d1, 0.1),
            stop_server(d2, 0.1),
            stop_server(d3, 0.1),
            stop_server(d4, 0.1),
            n.discover_bootnodes()
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        print(n.table.peers)

        expected_dict = {
            w1.verifying_key().hex(): 'inproc://testing1',
            w2.verifying_key().hex(): 'inproc://testing2',
            w3.verifying_key().hex(): 'inproc://testing3',
            w4.verifying_key().hex(): 'inproc://testing4'
        }

        self.assertDictEqual(n.table.peers, expected_dict)
