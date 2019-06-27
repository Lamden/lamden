from unittest import TestCase
import asyncio
from cilantro_ee.protocol.overlay.kademlia.discovery import *
import zmq
import zmq.asyncio
from cilantro_ee.protocol.wallet import Wallet
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
    def test_init(self):
        DiscoveryServer('inproc://testing', Wallet(), b'blah')

    def test_run_server(self):
        d = DiscoveryServer('inproc://testing',Wallet(), b'blah')

        tasks = asyncio.gather(timeout_bomb(), d.serve())
        run_silent_loop(tasks)

        d.ctx.destroy()

    def test_send_message_to_discovery(self):
        ctx = zmq.asyncio.Context()

        address = 'inproc://testing'

        d = DiscoveryServer('inproc://testing', Wallet(), b'blah', ctx=ctx)

        async def ping(msg, sleep):
            await asyncio.sleep(sleep)
            socket = ctx.socket(zmq.REQ)
            socket.connect(address)
            socket.send(msg)

            result = await socket.recv()
            self.assertTrue(result)

        tasks = asyncio.gather(ping(b'', TIME_UNIT), d.serve(), timeout_bomb())
        run_silent_loop(tasks)
        d.ctx.destroy()

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
        ctx = zmq.asyncio.Context()

        address = 'inproc://testing'

        wallet = Wallet()

        d = DiscoveryServer('inproc://testing', wallet, b'CORRECT_PEPPER', ctx=ctx)

        async def ping(msg, sleep):
            await asyncio.sleep(sleep)
            socket = ctx.socket(zmq.REQ)
            socket.connect(address)
            socket.send(msg)

            result = await socket.recv()
            self.assertTrue(verify_vk_pepper(result, b'CORRECT_PEPPER'))

        tasks = asyncio.gather(ping(b'', TIME_UNIT), d.serve(), timeout_bomb())
        run_silent_loop(tasks)
        d.ctx.destroy()

    def test_discovery_server_returns_wrong_vk_and_pepper(self):
        ctx = zmq.asyncio.Context()

        address = 'inproc://testing'

        wallet = Wallet()

        d = DiscoveryServer('inproc://testing', wallet, b'WRONG_PEPPER', ctx=ctx)

        async def ping(msg, sleep):
            await asyncio.sleep(sleep)
            socket = ctx.socket(zmq.REQ)
            socket.connect(address)
            socket.send(msg)

            result = await socket.recv()
            self.assertFalse(verify_vk_pepper(result, b'CORRECT_PEPPER'))

        tasks = asyncio.gather(ping(b'', TIME_UNIT), d.serve(), timeout_bomb())
        run_silent_loop(tasks)
        d.ctx.destroy()

    def test_discover_server_gets_correct_vk_from_msg_decoding(self):
        ctx = zmq.asyncio.Context()

        address = 'inproc://testing'

        wallet = Wallet()

        d = DiscoveryServer('inproc://testing', wallet, b'CORRECT_PEPPER', ctx=ctx)

        async def ping(msg, sleep):
            await asyncio.sleep(sleep)
            socket = ctx.socket(zmq.REQ)
            socket.connect(address)
            socket.send(msg)

            result = await socket.recv()

            vk, _ = unpack_pepper_msg(result)

            self.assertEqual(vk, wallet.verifying_key())

        tasks = asyncio.gather(ping(b'', TIME_UNIT), d.serve(), timeout_bomb())
        run_silent_loop(tasks)
        d.ctx.destroy()

    def test_async_ping_timeout_occurs_if_ip_isnt_online(self):
        ctx = zmq.asyncio.Context()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(ping(ip='inproc://dontexist',
                                     pepper=b'DOESNT_MATTER',
                                     ctx=ctx,
                                     timeout=0.05)
                                )
        ctx.destroy()

    def test_one_vk_returned_if_one_ip_is_online(self):
        ctx = zmq.asyncio.Context()
        wallet = Wallet()

        real_address = 'inproc://testing'
        fake_address = 'inproc://nahfam'

        d = DiscoveryServer(real_address, wallet, b'CORRECT_PEPPER', ctx=ctx)

        success_task = ping(ip=real_address,
                            pepper=b'CORRECT_PEPPER',
                            ctx=ctx,
                            timeout=0.1)

        failure_task = ping(ip=fake_address,
                            pepper=b'CORRECT_PEPPER',
                            ctx=ctx,
                            timeout=0.1)

        async def stop_server(timeout):
            await asyncio.sleep(timeout)
            d.stop()

        tasks = asyncio.gather(success_task, failure_task, d.serve(), stop_server(0.2))

        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(tasks)

        vk_ip1, vk_ip2, _, _ = results

        vk1, _ = vk_ip1
        vk2, _ = vk_ip2

        self.assertEqual(vk1, wallet.verifying_key())
        self.assertIsNone(vk2)

        ctx.destroy()
