from unittest import TestCase
from cilantro_ee.networking.discovery import *
import zmq
import zmq.asyncio
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.sockets.services import _socket
from time import sleep

TIME_UNIT = 0.01


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


class TestDiscoveryServer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        DiscoveryServer(_socket('tcp://127.0.0.1:10999'), Wallet(), b'blah')

    def test_run_server(self):
        d = DiscoveryServer(_socket('tcp://127.0.0.1:10999'), Wallet(), b'blah')

        tasks = asyncio.gather(timeout_bomb(), d.serve())
        run_silent_loop(tasks)

        d.ctx.destroy()

    def test_send_message_to_discovery(self):
        address = 'tcp://127.0.0.1:10999'

        d = DiscoveryServer(_socket('tcp://127.0.0.1:10999'), Wallet(), b'blah', ctx=self.ctx)

        async def ping(msg, sleep):
            await asyncio.sleep(sleep)
            socket = self.ctx.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 20)
            socket.connect(address)
            socket.send(msg)

            result = await socket.recv()
            self.assertTrue(result)

        tasks = asyncio.gather(ping(b'', TIME_UNIT), d.serve(), timeout_bomb())
        run_silent_loop(tasks)

    def test_verify_vk_pepper_correct_vk_pepper_message(self):
        wallet = Wallet()
        vk = wallet.verifying_key()
        pepper = b'TESTING_PEPPER'

        pepper_msg = vk + wallet.sign(pepper)

        self.assertTrue(verify_vk_pepper(pepper_msg, pepper))

    def test_verify_vk_pepper_wrong_vk_pepper_message(self):
        wallet = Wallet()
        vk = wallet.verifying_key()
        pepper = b'TESTING_PEPPER'

        pepper_msg = vk + wallet.sign(pepper)

        self.assertFalse(verify_vk_pepper(pepper_msg, b'WRONG_PEPPER'))

    def test_verify_vk_pepper_length_greater_than_32_bytes_assertion(self):
        with self.assertRaises(AssertionError):
            verify_vk_pepper(b'0', b'WRONG_PEPPER')

    def test_discovery_server_returns_correct_vk_and_pepper(self):
        address = 'tcp://127.0.0.1:10999'

        wallet = Wallet()

        d = DiscoveryServer(_socket('tcp://127.0.0.1:10999'), wallet, b'CORRECT_PEPPER', ctx=self.ctx)

        async def ping(msg, sleep):
            await asyncio.sleep(sleep)
            socket = self.ctx.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 20)
            socket.connect(address)
            socket.send(msg)

            result = await socket.recv()
            self.assertTrue(verify_vk_pepper(result, b'CORRECT_PEPPER'))

        tasks = asyncio.gather(ping(b'', TIME_UNIT), d.serve(), timeout_bomb())
        run_silent_loop(tasks)

    def test_discovery_server_returns_wrong_vk_and_pepper(self):

        address = 'inproc://testing'

        wallet = Wallet()

        d = DiscoveryServer(_socket('tcp://127.0.0.1:10999'), wallet, b'WRONG_PEPPER', ctx=self.ctx)

        async def ping(msg, sleep):
            await asyncio.sleep(sleep)
            socket = self.ctx.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 20)
            socket.connect(address)
            socket.send(msg)

            result = await socket.recv()
            self.assertFalse(verify_vk_pepper(result, b'CORRECT_PEPPER'))

        tasks = asyncio.gather(ping(b'', TIME_UNIT), d.serve(), timeout_bomb())
        run_silent_loop(tasks)

    def test_discover_server_gets_correct_vk_from_msg_decoding(self):
        address = 'tcp://127.0.0.1:10999'

        wallet = Wallet()

        d = DiscoveryServer(_socket('tcp://127.0.0.1:10999'), wallet, b'CORRECT_PEPPER', ctx=self.ctx)

        async def ping(msg, sleep):
            await asyncio.sleep(sleep)
            socket = self.ctx.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 20)
            socket.connect(address)
            socket.send(msg)

            result = await socket.recv()

            vk, _ = unpack_pepper_msg(result)

            self.assertEqual(vk, wallet.verifying_key())

        tasks = asyncio.gather(ping(b'', TIME_UNIT), d.serve(), timeout_bomb())
        run_silent_loop(tasks)

    def test_async_ping_timeout_occurs_if_ip_isnt_online(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(ping(_socket('inproc://dontexist'),
                                     pepper=b'DOESNT_MATTER',
                                     ctx=self.ctx,
                                     timeout=50,)
                                )

    def test_one_vk_returned_if_one_ip_is_online(self):
        wallet = Wallet()

        d = DiscoveryServer(_socket('tcp://127.0.0.1:10999'), wallet, b'CORRECT_PEPPER', ctx=self.ctx)

        success_task = ping(_socket('tcp://127.0.0.1:10999'),
                            pepper=b'CORRECT_PEPPER',
                            ctx=self.ctx,
                            timeout=300)

        failure_task = ping(_socket('tcp://127.0.0.1:20999'),
                            pepper=b'CORRECT_PEPPER',
                            ctx=self.ctx,
                            timeout=300)

        async def stop_server(timeout):
            await asyncio.sleep(timeout)
            d.stop()

        tasks = asyncio.gather(success_task, failure_task, d.serve(), stop_server(0.3))

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(tasks)

        vk_ip1, vk_ip2, _, _ = results

        _, vk1 = vk_ip1
        _, vk2 = vk_ip2

        self.assertEqual(vk1.hex(), wallet.verifying_key().hex())
        self.assertIsNone(vk2)

    def test_discover_nodes_found_one(self):
        address = _socket('tcp://127.0.0.1:10999')

        wallet = Wallet()

        d = DiscoveryServer(address, wallet, b'CORRECT_PEPPER', ctx=self.ctx)

        async def stop_server(timeout):
            await asyncio.sleep(timeout)
            d.stop()

        tasks = asyncio.gather(
            discover_nodes(ip_list=[address], pepper=b'CORRECT_PEPPER', ctx=self.ctx),
            d.serve(),
            stop_server(0.2)
        )

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(tasks)

        r = results[0]

        self.assertEqual(r[str(address)], wallet.verifying_key().hex())

    def test_discover_nodes_found_three(self):
        addresses = [_socket('tcp://127.0.0.1:10999'), _socket('tcp://127.0.0.1:11999'), _socket('tcp://127.0.0.1:12999')]
        wallets = [Wallet(), Wallet(), Wallet()]
        pepper = b'CORRECT_PEPPER'
        server_timeout = 0.3

        servers = [DiscoveryServer(addresses[0], wallets[0], pepper, ctx=self.ctx),
                   DiscoveryServer(addresses[1], wallets[1], pepper, ctx=self.ctx),
                   DiscoveryServer(addresses[2], wallets[2], pepper, ctx=self.ctx)]

        async def stop_server(s, timeout):
            await asyncio.sleep(timeout)
            s.stop()

        tasks = asyncio.gather(
            servers[0].serve(),
            servers[1].serve(),
            servers[2].serve(),
            stop_server(servers[0], server_timeout),
            stop_server(servers[1], server_timeout),
            stop_server(servers[2], server_timeout),
            discover_nodes(ip_list=addresses, pepper=pepper, ctx=self.ctx)
        )

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(tasks)

        r = results[-1]

        self.assertEqual(r[str(addresses[0])], wallets[0].verifying_key().hex())
        self.assertEqual(r[str(addresses[1])], wallets[1].verifying_key().hex())
        self.assertEqual(r[str(addresses[2])], wallets[2].verifying_key().hex())

    def test_discover_nodes_found_two_out_of_three(self):
        addresses = [_socket('tcp://127.0.0.1:10999'), _socket('tcp://127.0.0.1:11999'), _socket('tcp://127.0.0.1:12999')]
        addresses_wrong = [_socket('tcp://127.0.0.1:10999'), _socket('tcp://127.0.0.1:11999'), _socket('tcp://127.0.0.1:13999')]
        wallets = [Wallet(), Wallet(), Wallet()]
        pepper = b'CORRECT_PEPPER'
        server_timeout = 1

        servers = [DiscoveryServer(addresses[0], wallets[0], pepper, ctx=self.ctx),
                   DiscoveryServer(addresses[1], wallets[1], pepper, ctx=self.ctx),
                   DiscoveryServer(addresses[2], wallets[2], pepper, ctx=self.ctx)]

        async def stop_server(s, timeout):
            await asyncio.sleep(timeout)
            s.stop()

        tasks = asyncio.gather(
            servers[0].serve(),
            servers[1].serve(),
            servers[2].serve(),
            stop_server(servers[0], server_timeout),
            stop_server(servers[1], server_timeout),
            stop_server(servers[2], server_timeout),
            discover_nodes(ip_list=addresses_wrong, pepper=pepper, ctx=self.ctx)
        )

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(tasks)

        r = results[-1]

        self.assertEqual(r[str(addresses[0])], wallets[0].verifying_key().hex())
        self.assertEqual(r[str(addresses[1])], wallets[1].verifying_key().hex())
        self.assertIsNone(r.get(str(addresses[2])))

    def test_discover_nodes_none_found(self):
        addresses = [_socket('tcp://127.0.0.1:10999'), _socket('tcp://127.0.0.1:11999'), _socket('tcp://127.0.0.1:12999')]
        addresses_wrong = [_socket('tcp://127.0.0.1:15999'), _socket('tcp://127.0.0.1:14999'), _socket('tcp://127.0.0.1:13999')]
        wallets = [Wallet(), Wallet(), Wallet()]
        pepper = b'CORRECT_PEPPER'
        server_timeout = 1

        servers = [DiscoveryServer(addresses[0], wallets[0], pepper, ctx=self.ctx),
                   DiscoveryServer(addresses[1], wallets[1], pepper, ctx=self.ctx),
                   DiscoveryServer(addresses[2], wallets[2], pepper, ctx=self.ctx)]

        async def stop_server(s, timeout):
            await asyncio.sleep(timeout)
            s.stop()

        tasks = asyncio.gather(
            servers[0].serve(),
            servers[1].serve(),
            servers[2].serve(),
            stop_server(servers[0], server_timeout),
            stop_server(servers[1], server_timeout),
            stop_server(servers[2], server_timeout),
            discover_nodes(ip_list=addresses_wrong, pepper=pepper, ctx=self.ctx, timeout=500, retries=3)
        )

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(tasks)

        r = results[-1]

        self.assertIsNone(r.get(str(addresses[0])))
        self.assertIsNone(r.get(str(addresses[1])))
        self.assertIsNone(r.get(str(addresses[2])))

    def test_discover_works_with_ipc_sockets(self):
        wallet = Wallet()

        d = DiscoveryServer(_socket('ipc:///tmp/discovery'), wallet, b'CORRECT_PEPPER', ctx=self.ctx)

        success_task = ping(_socket('ipc:///tmp/discovery'),
                            pepper=b'CORRECT_PEPPER',
                            ctx=self.ctx,
                            timeout=300)

        failure_task = ping(_socket('tcp://127.0.0.1:20999'),
                            pepper=b'CORRECT_PEPPER',
                            ctx=self.ctx,
                            timeout=300)

        async def stop_server(timeout):
            await asyncio.sleep(timeout)
            d.stop()

        tasks = asyncio.gather(success_task, failure_task, d.serve(), stop_server(0.3))

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(tasks)

        vk_ip1, vk_ip2, _, _ = results

        _, vk1 = vk_ip1
        _, vk2 = vk_ip2

        self.assertEqual(vk1.hex(), wallet.verifying_key().hex())
        self.assertIsNone(vk2)

    def test_discover_works_with_blend_of_tcp_and_ipc(self):
        addresses = [_socket('ipc:///tmp/discover1'), _socket('tcp://127.0.0.1:11999'),
                     _socket('ipc:///tmp/woohoo')]
        wallets = [Wallet(), Wallet(), Wallet()]
        pepper = b'CORRECT_PEPPER'
        server_timeout = 0.3

        servers = [DiscoveryServer(addresses[0], wallets[0], pepper, ctx=self.ctx),
                   DiscoveryServer(addresses[1], wallets[1], pepper, ctx=self.ctx),
                   DiscoveryServer(addresses[2], wallets[2], pepper, ctx=self.ctx)]

        async def stop_server(s, timeout):
            await asyncio.sleep(timeout)
            s.stop()

        tasks = asyncio.gather(
            servers[0].serve(),
            servers[1].serve(),
            servers[2].serve(),
            stop_server(servers[0], server_timeout),
            stop_server(servers[1], server_timeout),
            stop_server(servers[2], server_timeout),
            discover_nodes(ip_list=addresses, pepper=pepper, ctx=self.ctx)
        )

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(tasks)

        r = results[-1]

        print(r)

        self.assertEqual(r[str(addresses[0])], wallets[0].verifying_key().hex())
        self.assertEqual(r[str(addresses[1])], wallets[1].verifying_key().hex())
        self.assertEqual(r[str(addresses[2])], wallets[2].verifying_key().hex())
