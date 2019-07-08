from unittest import TestCase
import asyncio
from cilantro_ee.protocol.overlay.kademlia.discovery import *
from cilantro_ee.protocol.overlay.kademlia.new_network import Network, PeerServer, KTable
from cilantro_ee.protocol.overlay.kademlia.discovery import DiscoveryServer
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

        self.assertDictEqual(n.table.peers, expected_dict)

    def test_peer_server_init(self):
        w = Wallet()
        t = KTable(data={'woo': 'hoo'})
        p = PeerServer(wallet=w, address='inproc://testing', event_publisher_address='tcp://*:8888',
                       table=t, ctx=self.ctx, linger=100, poll_timeout=100)

        tasks = asyncio.gather(
            p.serve(),
            stop_server(p, 0.1)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_peer_server_returns_self_when_asked(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ip='127.0.0.1', ctx=self.ctx, peer_service_port=10001, event_publisher_port=10002)

        find_message = ['find', w1.verifying_key().hex()]
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            stop_server(p1.peer_service, 0.3),
            services.get('tcp://127.0.0.1:10001', msg=find_message, ctx=self.ctx, timeout=300)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertEqual(response.get(w1.verifying_key().hex()), '127.0.0.1')

    def test_peer_server_returns_peer_when_asked(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ip='127.0.0.1', ctx=self.ctx, peer_service_port=10001, event_publisher_port=10002)

        w2 = Wallet()

        p1.peer_service.table.peers[w2.verifying_key().hex()] = 'inproc://goodtimes'

        find_message = ['find', w2.verifying_key().hex()]
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            stop_server(p1.peer_service, 0.3),
            services.get('tcp://127.0.0.1:10001', msg=find_message, ctx=self.ctx, timeout=300)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertEqual(response.get(w2.verifying_key().hex()), 'inproc://goodtimes')

    def test_peer_server_returns_all_peers_if_doesnt_have_it_or_more_than_response_amount(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ip='127.0.0.1', ctx=self.ctx, peer_service_port=10001, event_publisher_port=10002)

        test_dict = {
            'test': 'value',
            'another': 'one',
            'something': 'else'
        }

        p1.peer_service.table.peers = test_dict

        find_message = ['find', 'baloney']
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            stop_server(p1.peer_service, 0.3),
            services.get('tcp://127.0.0.1:10001', msg=find_message, ctx=self.ctx, timeout=300)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(test_dict, response)

    def test_peer_server_returns_max_response_keys(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ip='127.0.0.1', ctx=self.ctx, peer_service_port=10001, event_publisher_port=10002)

        test_dict = {
            'test': 'value',
            'another': 'one',
            'something': 'else'
        }

        expected_dict = {
            'test': 'value'
        }

        p1.peer_service.table.peers = test_dict
        p1.peer_service.table.response_size = 1

        find_message = ['find', 'tesZ']
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            stop_server(p1.peer_service, 0.2),
            services.get('tcp://127.0.0.1:10001', msg=find_message, ctx=self.ctx, timeout=200)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(expected_dict, response)

    def test_peer_server_returns_max_response_keys_many_keys(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ip='127.0.0.1', ctx=self.ctx, peer_service_port=10001, event_publisher_port=10002)

        test_dict = {
            '0': 'value',
            '1': 'one',
            '2': 'else',
            '3': 'value',
            '4': 'one',
            '5': 'else',
            '7': 'one',
            '8': 'else',
            '9': 'value',
            '10': 'one',
            '11': 'else',
            '12': 'value',
            '13': 'one',
            '14': 'else',
        }

        expected_dict = {
            '4': 'one',
            '5': 'else',
            '7': 'one',
            '2': 'else'
        }

        p1.peer_service.table.peers = test_dict
        p1.peer_service.table.response_size = 4

        find_message = ['find', '6']
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            stop_server(p1.peer_service, 0.2),
            services.get('tcp://127.0.0.1:10001', msg=find_message, ctx=self.ctx, timeout=200)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(expected_dict, response)

    def test_peer_table_updated_on_join_command(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ip='127.0.0.1', ctx=self.ctx, peer_service_port=10001, event_publisher_port=10002)

        w2 = Wallet()
        d = DiscoveryServer(wallet=w2, address='tcp://127.0.0.1:10999', pepper=PEPPER.encode(), ctx=self.ctx, linger=200)

        # 1. start network
        # 2. start discovery of other side
        # 3. send join request
        # 4. check to see if the data has been added

        join_message = ['join', (w2.verifying_key().hex(), 'tcp://127.0.0.1:10999')]
        join_message = json.dumps(join_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            d.serve(),
            services.get('tcp://127.0.0.1:10001', msg=join_message, ctx=self.ctx, timeout=1000),
            stop_server(p1.peer_service, 0.3),
            stop_server(d, 0.3)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertEqual(p1.peer_service.table.peers[w2.verifying_key().hex()], 'tcp://127.0.0.1:10999')

    def test_event_service_publisher_starts_up_on_init(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, ip='127.0.0.1', peer_service_port=10001, event_publisher_port=10002)

        test_subscriber = self.ctx.socket(zmq.SUB)
        test_subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        test_subscriber.connect('tcp://127.0.0.1:10002')

        # TCP takes a bit longer to bind and is prone to dropping messages...
        sleep(0.1)

        async def send():
            await p1.peer_service.event_publisher.send(b'waaaa')

        async def recv():
            return await test_subscriber.recv()

        tasks = asyncio.gather(
            send(),
            recv(),
            stop_server(p1.peer_service, 0.1)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], b'waaaa')

    def test_event_service_triggered_when_new_node_added(self):
        # Create Network service
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, ip='127.0.0.1', peer_service_port=10001, event_publisher_port=10002)

        # Create Discovery Server
        w2 = Wallet()
        d = DiscoveryServer(wallet=w2, address='tcp://127.0.0.1:10999', pepper=PEPPER.encode(), ctx=self.ctx,
                            poll_timeout=200, linger=200)

        # Create raw subscriber
        subscriber = self.ctx.socket(zmq.SUB)
        subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        subscriber.connect('tcp://127.0.0.1:10002')

        # TCP takes a bit longer to bind and is prone to dropping messages...
        sleep(0.1)

        # Construct the join RPC message
        join_message = ['join', (w2.verifying_key().hex(), 'tcp://127.0.0.1:10999')]
        join_message = json.dumps(join_message).encode()

        # Wrap recv() in an async
        async def recv():
            return await subscriber.recv()

        tasks = asyncio.gather(
            p1.peer_service.serve(),  # Start the PeerService which will process RPC and emit events
            d.serve(),  # Start Discovery so PeerService can verify they are online
            services.get('tcp://127.0.0.1:10001', msg=join_message, ctx=self.ctx, timeout=1000),  # Push out a join request
            stop_server(p1.peer_service, 0.1),
            stop_server(d, 0.1),
            recv()  # Collect the subscription result
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        expected_list = ['join', [w2.verifying_key().hex(), 'tcp://127.0.0.1:10999']]
        got_list = json.loads(res[-1].decode())

        self.assertListEqual(expected_list, got_list)

    def test_other_peers_add_new_nodes_when_join_event_occurs(self):
        # Create Network service
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, ip='127.0.0.1', peer_service_port=10001, event_publisher_port=10002)

        # Create Network service
        w2 = Wallet()
        p2 = Network(wallet=w2, ctx=self.ctx, ip='127.0.0.1', peer_service_port=10003, event_publisher_port=10004)

        p2.peer_service.event_service.add_subscription('tcp://127.0.0.1:10002')

        # Create Discovery Server
        w3 = Wallet()
        d = DiscoveryServer(wallet=w3, address='tcp://127.0.0.1:10999', pepper=PEPPER.encode(), ctx=self.ctx,
                            poll_timeout=200, linger=2000)

        # TCP takes a bit longer to bind and is prone to dropping messages...
        sleep(0.1)

        # Construct the join RPC message
        join_message = ['join', (w3.verifying_key().hex(), 'tcp://127.0.0.1:10999')]
        join_message = json.dumps(join_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.start(),
            p2.peer_service.start(),
            d.serve(),
            services.get('tcp://127.0.0.1:10001', msg=join_message, ctx=self.ctx, timeout=1000),
            stop_server(p1.peer_service, 0.3),
            stop_server(p2.peer_service, 0.3),
            stop_server(d, 0.3),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertTrue(w3.verifying_key().hex() in p2.peer_service.table.peers)

    def test_start_and_stopping_destroys_servers(self):
        # Create Network service
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, ip='127.0.0.1', peer_service_port=10001, event_publisher_port=10002)

        # Create Network service
        w2 = Wallet()
        p2 = Network(wallet=w2, ctx=self.ctx, ip='127.0.0.1', peer_service_port=10003, event_publisher_port=10004)

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        tasks = asyncio.gather(
            p1.peer_service.start(),

            p2.peer_service.start(),

            stop(p1, 0.3),
            stop(p2, 0.3)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)