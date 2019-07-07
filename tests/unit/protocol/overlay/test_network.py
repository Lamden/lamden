from unittest import TestCase
import asyncio
from cilantro_ee.protocol.overlay.kademlia.discovery import *
from cilantro_ee.protocol.overlay.kademlia.new_network import Network, PeerServer
from cilantro_ee.constants.overlay_network import PEPPER
from cilantro_ee.protocol.comm import services
import zmq
import zmq.asyncio
from cilantro_ee.protocol.wallet import Wallet
from time import sleep

import json

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

        d1 = DiscoveryServer('inproc://testing1', w1, PEPPER.encode(), ctx=self.ctx, linger=100, poll_timeout=100)
        d2 = DiscoveryServer('inproc://testing2', w2, PEPPER.encode(), ctx=self.ctx, linger=100, poll_timeout=100)
        d3 = DiscoveryServer('inproc://testing3', w3, PEPPER.encode(), ctx=self.ctx, linger=100, poll_timeout=100)
        d4 = DiscoveryServer('inproc://testing4', w4, PEPPER.encode(), ctx=self.ctx, linger=100, poll_timeout=100)

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

        expected_dict = {
            w1.verifying_key().hex(): 'inproc://testing1',
            w2.verifying_key().hex(): 'inproc://testing2',
            w3.verifying_key().hex(): 'inproc://testing3',
            w4.verifying_key().hex(): 'inproc://testing4'
        }

        self.assertDictEqual(n.peer_server.table.peers, expected_dict)

    def test_peer_server_init(self):
        w = Wallet()

        p = PeerServer(wallet=w, address='inproc://testing', event_address='inproc://testing2',
                       ctx=self.ctx, linger=100, poll_timeout=100)

        tasks = asyncio.gather(
            p.serve(),
            stop_server(p, 0.1)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_peer_server_returns_self_when_asked(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx)
        p1.peer_server.address = 'inproc://testing1'
        p1.peer_server.table.data = {
            w1.verifying_key().hex(): 'inproc://testing1'
        }

        find_message = ['find', w1.verifying_key().hex()]
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_server.serve(),
            stop_server(p1.peer_server, 0.1),
            services.get('inproc://testing1', msg=find_message, ctx=self.ctx, timeout=100)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertEqual(response.get(w1.verifying_key().hex()), 'inproc://testing1')

    def test_peer_server_returns_peer_when_asked(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx)
        p1.peer_server.address = 'inproc://testing1'
        p1.peer_server.table.data = {
            w1.verifying_key().hex(): 'inproc://testing1'
        }

        w2 = Wallet()

        p1.peer_server.table.peers[w2.verifying_key().hex()] = 'inproc://goodtimes'

        find_message = ['find', w2.verifying_key().hex()]
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_server.serve(),
            stop_server(p1.peer_server, 0.1),
            services.get('inproc://testing1', msg=find_message, ctx=self.ctx, timeout=100)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertEqual(response.get(w2.verifying_key().hex()), 'inproc://goodtimes')

    def test_peer_server_returns_all_peers_if_doesnt_have_it_or_more_than_response_amount(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx)
        p1.peer_server.address = 'inproc://testing1'
        p1.peer_server.table.data = {
            w1.verifying_key().hex(): 'inproc://testing1'
        }

        test_dict = {
            'test': 'value',
            'another': 'one',
            'something': 'else'
        }

        p1.peer_server.table.peers = test_dict

        find_message = ['find', 'baloney']
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_server.serve(),
            stop_server(p1.peer_server, 0.1),
            services.get('inproc://testing1', msg=find_message, ctx=self.ctx, timeout=100)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(test_dict, response)

    def test_peer_server_returns_max_response_keys(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx)
        p1.peer_server.address = 'inproc://testing1'
        p1.peer_server.table.data = {
            w1.verifying_key().hex(): 'inproc://testing1'
        }

        test_dict = {
            'test': 'value',
            'another': 'one',
            'something': 'else'
        }

        expected_dict = {
            'test': 'value'
        }

        p1.peer_server.table.peers = test_dict
        p1.peer_server.table.response_size = 1

        find_message = ['find', 'tesZ']
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_server.serve(),
            stop_server(p1.peer_server, 0.1),
            services.get('inproc://testing1', msg=find_message, ctx=self.ctx, timeout=100)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(expected_dict, response)