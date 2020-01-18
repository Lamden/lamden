from unittest import TestCase
from cilantro_ee.sockets.services import _socket
from cilantro_ee.networking.discovery import *
from cilantro_ee.networking.network import Network, PEPPER
from cilantro_ee.networking.parameters import NetworkParameters
from cilantro_ee.networking.peers import KTable, PeerServer
from cilantro_ee.networking.discovery import DiscoveryServer
from cilantro_ee.sockets import services
import zmq
import zmq.asyncio
from cilantro_ee.crypto.wallet import Wallet
from time import sleep
import json
import os

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

def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass

class TestNetworkService(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.get_event_loop()
        #asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        #self.loop.close()

    def test_setup(self):
        w = Wallet()
        Network(wallet=w, ctx=self.ctx)

    def test_bootstrap_nodes(self):
        w = Wallet()

        w1 = Wallet()
        w2 = Wallet()
        w3 = Wallet()
        w4 = Wallet()

        bootnodes = [_socket('tcp://127.0.0.1:10999'),
                     _socket('tcp://127.0.0.1:11999'),
                     _socket('tcp://127.0.0.1:12999'),
                     _socket('tcp://127.0.0.1:13999')]

        d1 = DiscoveryServer(bootnodes[0], w1, pepper=PEPPER.encode(), ctx=self.ctx, linger=1000, poll_timeout=1000)
        d2 = DiscoveryServer(bootnodes[1], w2, pepper=PEPPER.encode(), ctx=self.ctx, linger=1000, poll_timeout=1000)
        d3 = DiscoveryServer(bootnodes[2], w3, pepper=PEPPER.encode(), ctx=self.ctx, linger=1000, poll_timeout=1000)
        d4 = DiscoveryServer(bootnodes[3], w4, pepper=PEPPER.encode(), ctx=self.ctx, linger=1000, poll_timeout=1000)

        n = Network(wallet=w, ctx=self.ctx, bootnodes=bootnodes)

        tasks = asyncio.gather(
            d1.serve(),
            d2.serve(),
            d3.serve(),
            d4.serve(),
            stop_server(d1, 1),
            stop_server(d2, 1),
            stop_server(d3, 1),
            stop_server(d4, 1),
            n.discover_bootnodes(bootnodes)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        expected_dict = {
            w1.verifying_key().hex(): 'tcp://127.0.0.1:10999',
            w2.verifying_key().hex(): 'tcp://127.0.0.1:11999',
            w3.verifying_key().hex(): 'tcp://127.0.0.1:12999',
            w4.verifying_key().hex(): 'tcp://127.0.0.1:13999'
        }

        self.assertDictEqual(n.table.peers, expected_dict)

    def test_bootstrap_nodes_ipc(self):
        w = Wallet()

        w1 = Wallet()
        w2 = Wallet()
        w3 = Wallet()
        w4 = Wallet()

        bootnodes = [_socket('ipc:///tmp/one'),
                     _socket('ipc:///tmp/two'),
                     _socket('ipc:///tmp/three'),
                     _socket('ipc:///tmp/four')]

        d1 = DiscoveryServer(bootnodes[0], w1, pepper=PEPPER.encode(), ctx=self.ctx, linger=200, poll_timeout=200)
        d2 = DiscoveryServer(bootnodes[1], w2, pepper=PEPPER.encode(), ctx=self.ctx, linger=200, poll_timeout=200)
        d3 = DiscoveryServer(bootnodes[2], w3, pepper=PEPPER.encode(), ctx=self.ctx, linger=200, poll_timeout=200)
        d4 = DiscoveryServer(bootnodes[3], w4, pepper=PEPPER.encode(), ctx=self.ctx, linger=200, poll_timeout=200)

        n = Network(wallet=w, ctx=self.ctx, bootnodes=bootnodes)

        tasks = asyncio.gather(
            d1.serve(),
            d2.serve(),
            d3.serve(),
            d4.serve(),
            stop_server(d1, 1),
            stop_server(d2, 1),
            stop_server(d3, 1),
            stop_server(d4, 1),
            n.discover_bootnodes(bootnodes)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        expected_dict = {
            w1.verifying_key().hex(): 'ipc:///tmp/one',
            w2.verifying_key().hex(): 'ipc:///tmp/two',
            w3.verifying_key().hex(): 'ipc:///tmp/three',
            w4.verifying_key().hex(): 'ipc:///tmp/four'
        }

        self.assertDictEqual(n.table.peers, expected_dict)

    def test_peer_server_init(self):
        w = Wallet()
        t = KTable(data={'woo': 'hoo'})
        p = PeerServer(socket_id=_socket('tcp://127.0.0.1:10999'),
                       event_address=_socket('tcp://127.0.0.1:10888'),
                       wallet=w,
                       table=t, ctx=self.ctx, linger=100, poll_timeout=100)

        tasks = asyncio.gather(
            p.serve(),
            stop_server(p, 0.1)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_peer_server_returns_self_when_asked(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='tcp://127.0.0.1', ctx=self.ctx)

        find_message = ['find', w1.verifying_key().hex()]
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            stop_server(p1.peer_service, 0.3),
            services.get(_socket('tcp://127.0.0.1:10002'), msg=find_message, ctx=self.ctx, timeout=300)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertEqual(response.get(w1.verifying_key().hex()), 'tcp://127.0.0.1')

    def test_peer_server_returns_self_when_asked_ipc(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='ipc:///tmp', ctx=self.ctx)

        find_message = ['find', w1.verifying_key().hex()]
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            stop_server(p1.peer_service, 0.3),
            services.get(_socket('ipc:///tmp/peers'), msg=find_message, ctx=self.ctx, timeout=300)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertEqual(response.get(w1.verifying_key().hex()), 'ipc:///tmp')

    def test_peer_server_returns_peer_when_asked(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='tcp://127.0.0.1', ctx=self.ctx)

        w2 = Wallet()

        p1.peer_service.table.peers[w2.verifying_key().hex()] = 'inproc://goodtimes'

        find_message = ['find', w2.verifying_key().hex()]
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            stop_server(p1.peer_service, 0.3),
            services.get(_socket('tcp://127.0.0.1:10002'), msg=find_message, ctx=self.ctx, timeout=300)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertEqual(response.get(w2.verifying_key().hex()), 'inproc://goodtimes')

    def test_peer_server_returns_peer_when_asked_ipc(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='ipc:///tmp', ctx=self.ctx)

        w2 = Wallet()

        p1.peer_service.table.peers[w2.verifying_key().hex()] = 'inproc://goodtimes'

        find_message = ['find', w2.verifying_key().hex()]
        find_message = json.dumps(find_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            stop_server(p1.peer_service, 0.3),
            services.get(_socket('ipc:///tmp/peers'), msg=find_message, ctx=self.ctx, timeout=300)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertEqual(response.get(w2.verifying_key().hex()), 'inproc://goodtimes')

    def test_peer_server_returns_all_peers_if_doesnt_have_it_or_more_than_response_amount(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='tcp://127.0.0.1', ctx=self.ctx)

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
            services.get(_socket('tcp://127.0.0.1:10002'), msg=find_message, ctx=self.ctx, timeout=300)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(test_dict, response)

    def test_peer_server_returns_all_peers_if_doesnt_have_it_or_more_than_response_amount_ipc(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='ipc:///tmp', ctx=self.ctx)

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
            services.get(_socket('ipc:///tmp/peers'), msg=find_message, ctx=self.ctx, timeout=300)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(test_dict, response)

    def test_peer_server_returns_max_response_keys(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='tcp://127.0.0.1', ctx=self.ctx)

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
            services.get(_socket('tcp://127.0.0.1:10002'), msg=find_message, ctx=self.ctx, timeout=200)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(expected_dict, response)

    def test_peer_server_returns_max_response_keys_ipc(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='ipc:///tmp', ctx=self.ctx)

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
            services.get(_socket('ipc:////tmp/peers'), msg=find_message, ctx=self.ctx, timeout=200)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(expected_dict, response)

    def test_peer_server_returns_max_response_keys_many_keys(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='tcp://127.0.0.1', ctx=self.ctx)

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
            services.get(_socket('tcp://127.0.0.1:10002'), msg=find_message, ctx=self.ctx, timeout=200)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(expected_dict, response)

    def test_peer_server_returns_max_response_keys_many_keys_ipc(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='ipc:///tmp', ctx=self.ctx)

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
            services.get(_socket('ipc:///tmp/peers'), msg=find_message, ctx=self.ctx, timeout=200)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        response = res[-1]
        response = response.decode()
        response = json.loads(response)

        self.assertDictEqual(expected_dict, response)

    def test_peer_table_updated_on_join_command(self):
        # Network params issue
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='tcp://127.0.0.1', ctx=self.ctx)

        w2 = Wallet()
        d = DiscoveryServer(wallet=w2, socket_id=_socket('tcp://127.0.0.1:10999'), pepper=PEPPER.encode(), ctx=self.ctx, linger=200)

        # 1. start network
        # 2. start discovery of other side
        # 3. send join request
        # 4. check to see if the data has been added

        join_message = ['join', (w2.verifying_key().hex(), 'tcp://127.0.0.1:10999')]
        join_message = json.dumps(join_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            d.serve(),
            services.get(_socket('tcp://127.0.0.1:10002'), msg=join_message, ctx=self.ctx, timeout=1000),
            stop_server(p1.peer_service, 0.3),
            stop_server(d, 0.3)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertEqual(p1.peer_service.table.peers[w2.verifying_key().hex()], 'tcp://127.0.0.1:10999')

    def test_peer_table_updated_on_join_command_ipc(self):
        # Network params issue
        w1 = Wallet()
        p1 = Network(wallet=w1, socket_base='ipc:///tmp', ctx=self.ctx)

        w2 = Wallet()
        d = DiscoveryServer(wallet=w2, socket_id=_socket('ipc:///tmp/xxx'), pepper=PEPPER.encode(), ctx=self.ctx, linger=200)

        # 1. start network
        # 2. start discovery of other side
        # 3. send join request
        # 4. check to see if the data has been added

        join_message = ['join', (w2.verifying_key().hex(), 'ipc:///tmp/xxx')]
        join_message = json.dumps(join_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.serve(),
            d.serve(),
            services.get(_socket('ipc:///tmp/peers'), msg=join_message, ctx=self.ctx, timeout=1000),
            stop_server(p1.peer_service, 0.3),
            stop_server(d, 0.3)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertEqual(p1.peer_service.table.peers[w2.verifying_key().hex()], 'ipc:///tmp/xxx')

    def test_event_service_publisher_starts_up_on_init(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        test_subscriber = self.ctx.socket(zmq.SUB)
        test_subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        test_subscriber.connect('tcp://127.0.0.1:10003')

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

    def test_event_service_publisher_starts_up_on_init_ipc(self):
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='ipc:///tmp')

        test_subscriber = self.ctx.socket(zmq.SUB)
        test_subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        test_subscriber.connect('ipc:///tmp/events')

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
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        # Create Discovery Server
        w2 = Wallet()
        d = DiscoveryServer(wallet=w2, socket_id=_socket('tcp://127.0.0.1:10999'), pepper=PEPPER.encode(), ctx=self.ctx,
                            poll_timeout=2000, linger=200)

        # Create raw subscriber
        subscriber = self.ctx.socket(zmq.SUB)
        subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        subscriber.connect('tcp://127.0.0.1:10003')

        # TCP takes a bit longer to bind and is prone to dropping messages...
        sleep(0.3)

        # Construct the join RPC message
        join_message = ['join', (w2.verifying_key().hex(), 'tcp://127.0.0.1:10999')]
        join_message = json.dumps(join_message).encode()

        # Wrap recv() in an async
        async def recv():
            msg = await subscriber.recv()
            return msg

        tasks = asyncio.gather(
            p1.peer_service.start(),  # Start the PeerService which will process RPC and emit events
            d.serve(),  # Start Discovery so PeerService can verify they are online
            services.get(_socket('tcp://127.0.0.1:10002'), msg=join_message, ctx=self.ctx, timeout=3000),  # Push out a join request
            stop_server(p1.peer_service, 1),
            stop_server(d, 1),
            recv()  # Collect the subscription result
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        expected_list = ['join', [w2.verifying_key().hex(), 'tcp://127.0.0.1:10999']]
        got_list = json.loads(res[-1].decode())

        self.assertListEqual(expected_list, got_list)

    def test_event_service_triggered_when_new_node_added_ipc(self):
        # Create Network service
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='ipc:///tmp')

        # Create Discovery Server
        w2 = Wallet()
        d = DiscoveryServer(wallet=w2, socket_id=_socket('ipc:///tmp/xxx'), pepper=PEPPER.encode(), ctx=self.ctx,
                            poll_timeout=2000, linger=200)

        # Create raw subscriber
        subscriber = self.ctx.socket(zmq.SUB)
        subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        subscriber.connect('ipc:///tmp/events')

        # TCP takes a bit longer to bind and is prone to dropping messages...
        sleep(0.3)

        # Construct the join RPC message
        join_message = ['join', (w2.verifying_key().hex(), 'ipc:///tmp/xxx')]
        join_message = json.dumps(join_message).encode()

        # Wrap recv() in an async
        async def recv():
            msg = await subscriber.recv()
            return msg

        tasks = asyncio.gather(
            p1.peer_service.start(),  # Start the PeerService which will process RPC and emit events
            d.serve(),  # Start Discovery so PeerService can verify they are online
            services.get(_socket('ipc:///tmp/peers'), msg=join_message, ctx=self.ctx, timeout=3000),  # Push out a join request
            stop_server(p1.peer_service, 1),
            stop_server(d, 1),
            recv()  # Collect the subscription result
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        expected_list = ['join', [w2.verifying_key().hex(), 'ipc:///tmp/xxx']]
        got_list = json.loads(res[-1].decode())

        self.assertListEqual(expected_list, got_list)

    def test_other_peers_add_new_nodes_when_join_event_occurs(self):
        # Create Network service
        w1 = Wallet()
        n1 = NetworkParameters(peer_port=10001, event_port=10002, discovery_port=10999)
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n1)

        # Create Network service
        w2 = Wallet()
        n2 = NetworkParameters(peer_port=10003, event_port=10004)
        p2 = Network(wallet=w2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n2)

        p2.peer_service.event_service.add_subscription(_socket('tcp://127.0.0.1:10002'))

        # Create Discovery Server
        w3 = Wallet()
        d = DiscoveryServer(wallet=w3, socket_id=_socket('tcp://127.0.0.1:10999'), pepper=PEPPER.encode(), ctx=self.ctx,
                            poll_timeout=2000, linger=2000)

        # TCP takes a bit longer to bind and is prone to dropping messages...
        sleep(1)

        # Construct the join RPC message
        join_message = ['join', (w3.verifying_key().hex(), 'tcp://127.0.0.1:10999')]
        join_message = json.dumps(join_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.start(),
            p2.peer_service.start(),
            d.serve(),
            services.get(_socket('tcp://127.0.0.1:10001'), msg=join_message, ctx=self.ctx, timeout=1000),
            stop_server(p1.peer_service, 2),
            stop_server(p2.peer_service, 2),
            stop_server(d, 2),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertTrue(w3.verifying_key().hex() in p2.peer_service.table.peers)

    def test_other_peers_add_new_nodes_when_join_event_occurs_ipc(self):
        # Create Network service
        w1 = Wallet()
        n1 = NetworkParameters(peer_ipc='peers1', event_ipc='events1', discovery_ipc='discovery1')
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='ipc:///tmp', params=n1)

        # Create Network service
        w2 = Wallet()
        n2 = NetworkParameters(peer_ipc='peers2', event_port='events2')
        p2 = Network(wallet=w2, ctx=self.ctx, socket_base='ipc:///tmp', params=n2)

        p2.peer_service.event_service.add_subscription(_socket('ipc:///tmp/events1'))

        # Create Discovery Server
        w3 = Wallet()
        d = DiscoveryServer(wallet=w3, socket_id=_socket('ipc:///tmp/discovery1'), pepper=PEPPER.encode(), ctx=self.ctx,
                            poll_timeout=2000, linger=2000)

        # TCP takes a bit longer to bind and is prone to dropping messages...
        sleep(1)

        # Construct the join RPC message
        join_message = ['join', (w3.verifying_key().hex(), 'ipc:///tmp/discovery1')]
        join_message = json.dumps(join_message).encode()

        tasks = asyncio.gather(
            p1.peer_service.start(),
            p2.peer_service.start(),
            d.serve(),
            services.get(_socket('ipc:///tmp/peers1'), msg=join_message, ctx=self.ctx, timeout=1000),
            stop_server(p1.peer_service, 2),
            stop_server(p2.peer_service, 2),
            stop_server(d, 2),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertTrue(w3.verifying_key().hex() in p2.peer_service.table.peers)

    def test_start_and_stopping_destroys_servers(self):
        # Create Network service
        w1 = Wallet()
        n1 = NetworkParameters(peer_port=10001, event_port=10002)
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n1)

        # Create Network service
        w2 = Wallet()
        n2 = NetworkParameters(peer_port=10003, event_port=10004)
        p2 = Network(wallet=w2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n2)

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

    def test_start_and_stopping_destroys_servers_ipc(self):
        # Create Network service
        w1 = Wallet()
        n1 = NetworkParameters(peer_ipc='peers1', event_ipc='events1', discovery_ipc='discovery1')
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='ipc:///tmp', params=n1)

        # Create Network service
        w2 = Wallet()
        n2 = NetworkParameters(peer_ipc='peers2', event_port='events2')
        p2 = Network(wallet=w2, ctx=self.ctx, socket_base='ipc:///tmp', params=n2)

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

    def test_find_node_returns_self_if_asked_on_peer_address_and_self_is_the_value(self):
        # Create Network service
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        async def get():
            return await p1.find_node(p1.peer_service_address, w1.verifying_key().hex())

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(get())

        self.assertEqual(res.get(w1.verifying_key().hex()), 'tcp://127.0.0.1')

    def test_find_node_returns_self_if_asked_on_peer_address_and_self_is_the_value_ipc(self):
        # Create Network service
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='ipc:///tmp')

        async def get():
            return await p1.find_node(p1.peer_service_address, w1.verifying_key().hex())

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(get())

        self.assertEqual(res.get(w1.verifying_key().hex()), 'ipc:///tmp')

    def test_find_node_gets_node_from_self_if_asked_from_self_and_has_it_as_peer(self):
        # Create Network service
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1')

        w2 = Wallet()
        p1.table.peers[w2.verifying_key().hex()] = '9.9.9.9'

        async def get():
            return await p1.find_node(p1.peer_service_address, w2.verifying_key().hex())

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(get())

        self.assertEqual(res.get(w2.verifying_key().hex()), '9.9.9.9')

    def test_find_node_gets_node_from_self_if_asked_from_self_and_has_it_as_peer_ipc(self):
        # Create Network service
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='ipc:///tmp')

        w2 = Wallet()
        p1.table.peers[w2.verifying_key().hex()] = 'ipc:///tmp123'

        async def get():
            return await p1.find_node(p1.peer_service_address, w2.verifying_key().hex())

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(get())

        self.assertEqual(res.get(w2.verifying_key().hex()), 'ipc:///tmp123')

    def test_find_node_requests_from_others_and_returns_key_if_they_have_it(self):
        # Create Network service
        w1 = Wallet()
        n1 = NetworkParameters(peer_port=10001, event_port=10002)
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n1)

        # Create Network service
        w2 = Wallet()
        n2 = NetworkParameters(peer_port=10003, event_port=10004)
        p2 = Network(wallet=w2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n2)

        async def get():
            return await p1.find_node(_socket('tcp://127.0.0.1:10003'), w2.verifying_key().hex())

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        tasks = asyncio.gather(
            p1.peer_service.start(),

            p2.peer_service.start(),
            get(),
            stop(p1, 0.3),
            stop(p2, 0.3),

        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[2].get(w2.verifying_key().hex()), 'tcp://127.0.0.1')

    def test_find_node_requests_from_others_and_returns_key_if_they_have_it_ipc(self):
        # Create Network service
        w1 = Wallet()
        n1 = NetworkParameters(peer_ipc='peers1', event_ipc='events1', discovery_ipc='discovery1')
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='ipc:///tmp', params=n1)

        # Create Network service
        w2 = Wallet()
        n2 = NetworkParameters(peer_ipc='peers2', event_port='events2')
        p2 = Network(wallet=w2, ctx=self.ctx, socket_base='ipc:///tmp', params=n2)

        async def get():
            return await p1.find_node(_socket('ipc:///tmp/peers2'), w2.verifying_key().hex())

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        tasks = asyncio.gather(
            p1.peer_service.start(),

            p2.peer_service.start(),
            get(),
            stop(p1, 0.3),
            stop(p2, 0.3),

        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[2].get(w2.verifying_key().hex()), 'ipc:///tmp')

    def test_find_node_fails_if_cant_find_and_retries_are_up(self):
        # Create Network service
        w1 = Wallet()
        n1 = NetworkParameters(peer_port=10001, event_port=10002)
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n1)

        # Create Network service
        w2 = Wallet()
        n2 = NetworkParameters(peer_port=10003, event_port=10004)
        p2 = Network(wallet=w2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n2)

        w3 = Wallet()

        async def get():
            return await p1.find_node(_socket('tcp://127.0.0.1:10003'), w3.verifying_key().hex(), retries=1)

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        tasks = asyncio.gather(
            p1.peer_service.start(),

            p2.peer_service.start(),
            get(),
            stop(p1, 0.3),
            stop(p2, 0.3),

        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertIsNone(res[2])

    def test_recursive_crawl_works_to_proper_depth(self):
        # Create Network service
        w1 = Wallet()
        n1 = NetworkParameters(peer_port=10001, event_port=10002)
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n1)

        # Create Network service
        w2 = Wallet()
        n2 = NetworkParameters(peer_port=10003, event_port=10004)
        p2 = Network(wallet=w2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n2)

        # Create Network service
        w3 = Wallet()
        n3 = NetworkParameters(peer_port=10005, event_port=10006)
        p3 = Network(wallet=w3, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n3)

        # Create Network service
        w4 = Wallet()
        n4 = NetworkParameters(peer_port=10007, event_port=10008)
        p4 = Network(wallet=w4, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n4)

        # 2 tries <- info in this node should be returned
        w5 = Wallet()

        # Add node info in each peer service to 'chain' them together
        p2.table.peers[w3.verifying_key().hex()] = 'tcp://127.0.0.1:10005'
        p3.table.peers[w4.verifying_key().hex()] = 'tcp://127.0.0.1:10007'
        p4.table.peers[w5.verifying_key().hex()] = 'you found me!'

        async def get():
            return await p1.find_node(_socket('tcp://127.0.0.1:10003'), w5.verifying_key().hex(), retries=2)

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        timeout = 0.3

        tasks = asyncio.gather(
            p1.peer_service.start(),
            p2.peer_service.start(),
            p3.peer_service.start(),
            p4.peer_service.start(),
            get(),
            stop(p1, timeout),
            stop(p2, timeout),
            stop(p3, timeout),
            stop(p4, timeout),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[4].get(w5.verifying_key().hex()), 'you found me!')

    def test_recursive_crawl_works_to_proper_depth_ipc(self):
        # Create Network service
        n1 = '/tmp/n1'
        try:
            os.mkdir('/tmp/n1')
        except:
            pass
        w1 = Wallet()
        p1 = Network(wallet=w1, ctx=self.ctx, socket_base=f'ipc://{n1}')

        # Create Network service
        n2 = '/tmp/n2'
        try:
            os.mkdir('/tmp/n2')
        except:
            pass
        w2 = Wallet()
        p2 = Network(wallet=w2, ctx=self.ctx, socket_base=f'ipc://{n2}')

        n3 = '/tmp/n3'
        try:
            os.mkdir('/tmp/n3')
        except:
            pass
        w3 = Wallet()
        p3 = Network(wallet=w3, ctx=self.ctx, socket_base=f'ipc://{n3}')

        n4 = '/tmp/n4'
        try:
            os.mkdir('/tmp/n4')
        except:
            pass
        w4 = Wallet()
        p4 = Network(wallet=w4, ctx=self.ctx, socket_base=f'ipc://{n4}')

        # 2 tries <- info in this node should be returned
        w5 = Wallet()

        # Add node info in each peer service to 'chain' them together
        p2.table.peers[w3.verifying_key().hex()] = 'ipc:///tmp/n3'
        p3.table.peers[w4.verifying_key().hex()] = 'ipc:///tmp/n4'
        p4.table.peers[w5.verifying_key().hex()] = 'you found me!'

        async def get():
            return await p1.find_node(_socket('ipc:///tmp/n2/peers'), w5.verifying_key().hex(), retries=2)

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        timeout = 0.3

        tasks = asyncio.gather(
            p1.peer_service.start(),
            p2.peer_service.start(),
            p3.peer_service.start(),
            p4.peer_service.start(),
            get(),
            stop(p1, timeout),
            stop(p2, timeout),
            stop(p3, timeout),
            stop(p4, timeout),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[4].get(w5.verifying_key().hex()), 'you found me!')

    def test_wait_for_quorum_to_succeed_only_one_master(self):
        # 0 tries
        mnw1 = Wallet()
        n1 = NetworkParameters(peer_port=10001, event_port=10002)
        mn1 = Network(wallet=mnw1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n1)

        # 1 try
        mnw2 = Wallet()
        n2 = NetworkParameters(peer_port=10003, event_port=10004)
        mn2 = Network(wallet=mnw2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n2)

        dw1 = Wallet()
        n3 = NetworkParameters(peer_port=10005, event_port=10006)
        d1 = Network(wallet=dw1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n3)

        # 2 tries <- info in this node should be returned
        dw2 = Wallet()
        n4 = NetworkParameters(peer_port=10007, event_port=10008)
        d2 = Network(wallet=dw2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n4)

        async def get():
            return await mn1.wait_for_quorum(1, 0, [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()],
                                             [dw1.verifying_key().hex(), dw2.verifying_key().hex()],
                                             initial_peers=[_socket('tcp://127.0.0.1:10003')])

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        timeout = 0.3

        tasks = asyncio.gather(
            mn1.peer_service.start(),
            mn2.peer_service.start(),
            d1.peer_service.start(),
            d2.peer_service.start(),
            get(),
            stop(mn1, timeout),
            stop(mn2, timeout),
            stop(d1, timeout),
            stop(d1, timeout),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertIn(mnw2.verifying_key().hex(), mn1.table.peers)

    def test_wait_for_quorum_to_succeed_only_one_master_ipc(self):
        # 0 tries
        n1 = '/tmp/n1'
        try:
            os.mkdir('/tmp/n1')
        except:
            pass
        mnw1 = Wallet()
        mn1 = Network(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}')

        n2 = '/tmp/n2'
        try:
            os.mkdir('/tmp/n2')
        except:
            pass
        mnw2 = Wallet()
        mn2 = Network(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}')

        n3 = '/tmp/n3'
        try:
            os.mkdir('/tmp/n3')
        except:
            pass
        dw1 = Wallet()
        d1 = Network(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}')

        n4 = '/tmp/n4'
        try:
            os.mkdir('/tmp/n4')
        except:
            pass
        dw2 = Wallet()
        d2 = Network(wallet=dw2, ctx=self.ctx, socket_base=f'ipc://{n4}')

        async def get():
            return await mn1.wait_for_quorum(1, 0, [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()],
                                             [dw1.verifying_key().hex(), dw2.verifying_key().hex()],
                                             initial_peers=[_socket('ipc:///tmp/n2/peers')])

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        timeout = 0.3

        tasks = asyncio.gather(
            mn1.peer_service.start(),
            mn2.peer_service.start(),
            d1.peer_service.start(),
            d2.peer_service.start(),
            get(),
            stop(mn1, timeout),
            stop(mn2, timeout),
            stop(d1, timeout),
            stop(d1, timeout),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertIn(mnw2.verifying_key().hex(), mn1.table.peers)

    def test_wait_for_quorum_with_initial_nodes_being_single_node(self):
        # 0 tries
        mnw1 = Wallet()
        n1 = NetworkParameters(peer_port=10001, event_port=10002)
        mn1 = Network(wallet=mnw1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n1)

        # 1 try
        mnw2 = Wallet()
        n2 = NetworkParameters(peer_port=10003, event_port=10004)
        mn2 = Network(wallet=mnw2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n2)

        dw1 = Wallet()
        n3 = NetworkParameters(peer_port=10005, event_port=10006)
        d1 = Network(wallet=dw1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n3)

        # 2 tries <- info in this node should be returned
        dw2 = Wallet()
        n4 = NetworkParameters(peer_port=10007, event_port=10008)
        d2 = Network(wallet=dw2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n4)

        # Add various info to each so that a crawl is successful
        mn2.table.peers[dw1.verifying_key().hex()] = 'tcp://127.0.0.1:10005'
        d1.table.peers[dw2.verifying_key().hex()] = 'tcp://127.0.0.1:10007'

        async def get():
            return await mn1.wait_for_quorum(2, 2, [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()],
                                             [dw1.verifying_key().hex(), dw2.verifying_key().hex()],
                                             initial_peers=[_socket('tcp://127.0.0.1:10003')])

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        timeout = 0.3

        tasks = asyncio.gather(
            mn1.peer_service.start(),
            mn2.peer_service.start(),
            d1.peer_service.start(),
            d2.peer_service.start(),
            get(),
            stop(mn1, timeout),
            stop(mn2, timeout),
            stop(d1, timeout),
            stop(d1, timeout),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertIn(mnw2.verifying_key().hex(), mn1.table.peers)
        self.assertIn(dw1.verifying_key().hex(), mn1.table.peers)
        self.assertIn(dw2.verifying_key().hex(), mn1.table.peers)

    def test_wait_for_quorum_with_initial_nodes_being_single_node_ipc(self):
        # 0 tries
        n1 = '/tmp/n1'
        try:
            os.mkdir('/tmp/n1')
        except:
            pass
        mnw1 = Wallet()
        mn1 = Network(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}')

        n2 = '/tmp/n2'
        try:
            os.mkdir('/tmp/n2')
        except:
            pass
        mnw2 = Wallet()
        mn2 = Network(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}')

        n3 = '/tmp/n3'
        try:
            os.mkdir('/tmp/n3')
        except:
            pass
        dw1 = Wallet()
        d1 = Network(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}')

        n4 = '/tmp/n4'
        try:
            os.mkdir('/tmp/n4')
        except:
            pass
        dw2 = Wallet()
        d2 = Network(wallet=dw2, ctx=self.ctx, socket_base=f'ipc://{n4}')

        # Add various info to each so that a crawl is successful
        mn2.table.peers[dw1.verifying_key().hex()] = 'ipc:///tmp/n3/peers'
        d1.table.peers[dw2.verifying_key().hex()] = 'ipc:///tmp/n4/peers'

        async def get():
            return await mn1.wait_for_quorum(2, 2, [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()],
                                             [dw1.verifying_key().hex(), dw2.verifying_key().hex()],
                                             initial_peers=[_socket('ipc:///tmp/n2/peers')])

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        timeout = 0.3

        tasks = asyncio.gather(
            mn1.peer_service.start(),
            mn2.peer_service.start(),
            d1.peer_service.start(),
            d2.peer_service.start(),
            get(),
            stop(mn1, timeout),
            stop(mn2, timeout),
            stop(d1, timeout),
            stop(d1, timeout),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertIn(mnw2.verifying_key().hex(), mn1.table.peers)
        self.assertIn(dw1.verifying_key().hex(), mn1.table.peers)
        self.assertIn(dw2.verifying_key().hex(), mn1.table.peers)

    def test_wait_for_quorum_resolves_when_late_joiner(self):
        # 0 tries
        mnw1 = Wallet()
        n1 = NetworkParameters(peer_port=10001, event_port=10002)
        mn1 = Network(wallet=mnw1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n1)

        # 1 try
        mnw2 = Wallet()
        n2 = NetworkParameters(peer_port=10003, event_port=10004)
        mn2 = Network(wallet=mnw2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n2)

        dw1 = Wallet()
        n3 = NetworkParameters(peer_port=10005, event_port=10006)
        d1 = Network(wallet=dw1, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n3)

        # 2 tries <- info in this node should be returned
        dw2 = Wallet()
        n4 = NetworkParameters(peer_port=10007, event_port=10008)
        d2 = Network(wallet=dw2, ctx=self.ctx, socket_base='tcp://127.0.0.1', params=n4)
        # Add various info to each so that a crawl is successful
        mn2.table.peers[dw1.verifying_key().hex()] = 'tcp://127.0.0.1:10005'
        d1.table.peers[dw2.verifying_key().hex()] = 'tcp://127.0.0.1:10007'

        async def get():
            return await mn1.wait_for_quorum(2, 2, [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()],
                                             [dw1.verifying_key().hex(), dw2.verifying_key().hex()],
                                             initial_peers=[_socket('tcp://127.0.0.1:10003')])

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        async def start_late(n: Network, s):
            await asyncio.sleep(s)
            await n.peer_service.start()

        timeout = 0.5

        tasks = asyncio.gather(
            mn1.peer_service.start(),
            start_late(mn2, 0.1),
            start_late(d1, 0.2),
            start_late(d2, 0.3),
            get(),
            stop(mn1, timeout),
            stop(mn2, timeout),
            stop(d1, timeout),
            stop(d1, timeout),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertIn(mnw2.verifying_key().hex(), mn1.table.peers)
        self.assertIn(dw1.verifying_key().hex(), mn1.table.peers)
        self.assertIn(dw2.verifying_key().hex(), mn1.table.peers)

    def test_wait_for_quorum_resolves_when_late_joiner_ipc(self):
        # 0 tries

        n1 = '/tmp/n1'
        make_ipc(n1)

        mnw1 = Wallet()
        mn1 = Network(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}')

        n2 = '/tmp/n2'
        make_ipc(n2)

        mnw2 = Wallet()
        mn2 = Network(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}')

        n3 = '/tmp/n3'
        make_ipc(n3)

        dw1 = Wallet()
        d1 = Network(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}')

        n4 = '/tmp/n4'
        make_ipc(n4)

        dw2 = Wallet()
        d2 = Network(wallet=dw2, ctx=self.ctx, socket_base=f'ipc://{n4}')

        # Add various info to each so that a crawl is successful
        mn2.table.peers[dw1.verifying_key().hex()] = 'ipc:///tmp/n3/peers'
        d1.table.peers[dw2.verifying_key().hex()] = 'ipc:///tmp/n4/peers'

        async def get():
            return await mn1.wait_for_quorum(2, 2, [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()],
                                             [dw1.verifying_key().hex(), dw2.verifying_key().hex()],
                                             initial_peers=[_socket('ipc:///tmp/n2/peers')])

        async def stop(n: Network, s):
            await asyncio.sleep(s)
            n.peer_service.stop()

        async def start_late(n: Network, s):
            await asyncio.sleep(s)
            await n.peer_service.start()

        timeout = 0.5

        tasks = asyncio.gather(
            mn1.peer_service.start(),
            start_late(mn2, 0.1),
            start_late(d1, 0.2),
            start_late(d2, 0.3),
            get(),
            stop(mn1, timeout),
            stop(mn2, timeout),
            stop(d1, timeout),
            stop(d1, timeout),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertIn(mnw2.verifying_key().hex(), mn1.table.peers)
        self.assertIn(dw1.verifying_key().hex(), mn1.table.peers)
        self.assertIn(dw2.verifying_key().hex(), mn1.table.peers)

    # def test quorum made and another node wants to connect afterwards

    def test_network_start(self):
        # 4 nodes
        # 2 bootnodes
        # 2 mns, 2 delegates

        bootnodes = ['ipc:///tmp/n1', 'ipc:///tmp/n3']

        mnw1 = Wallet()
        mnw2 = Wallet()
        masternodes = [mnw1.verifying_key().hex(), mnw2.verifying_key().hex()]

        dw1 = Wallet()
        dw2 = Wallet()
        delegates = [dw1.verifying_key().hex(), dw2.verifying_key().hex()]

        n1 = '/tmp/n1'
        make_ipc(n1)
        mn1 = Network(wallet=mnw1, ctx=self.ctx, socket_base=f'ipc://{n1}',
                      bootnodes=bootnodes, mn_to_find=masternodes, del_to_find=delegates)

        n2 = '/tmp/n2'
        make_ipc(n2)
        mn2 = Network(wallet=mnw2, ctx=self.ctx, socket_base=f'ipc://{n2}',
                      bootnodes=bootnodes, mn_to_find=masternodes, del_to_find=delegates)

        n3 = '/tmp/n3'
        make_ipc(n3)
        d1 = Network(wallet=dw1, ctx=self.ctx, socket_base=f'ipc://{n3}',
                     bootnodes=bootnodes, mn_to_find=masternodes, del_to_find=delegates)

        n4 = '/tmp/n4'
        make_ipc(n4)
        d2 = Network(wallet=dw2, ctx=self.ctx, socket_base=f'ipc://{n4}',
                     bootnodes=bootnodes, mn_to_find=masternodes, del_to_find=delegates)

        # should test to see all ready signals are recieved
        tasks = asyncio.gather(
            mn1.start(),
            mn2.start(),
            d1.start(),
            d2.start()
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)
