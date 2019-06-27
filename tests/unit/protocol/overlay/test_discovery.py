from unittest import TestCase
import asyncio
from cilantro_ee.protocol.overlay.kademlia.discovery import DiscoveryServer, verify_vk_pepper
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
        print(e)
        pass
    sleep(s)


async def timeout_bomb(sleep=TIME_UNIT*2):
    await asyncio.sleep(sleep)
    asyncio.get_event_loop().close()


class TestDiscoveryServer(TestCase):
    def test_init(self):
        DiscoveryServer('inproc://testing', Wallet(), b'blah')

    def test_run_server(self):
        d = DiscoveryServer('inproc://testing',Wallet(), b'blah')

        tasks = asyncio.gather(timeout_bomb(), d.serve())
        run_silent_loop(tasks)

        d.destroy()

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
        d.destroy()

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
        d.destroy()

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
        d.destroy()
