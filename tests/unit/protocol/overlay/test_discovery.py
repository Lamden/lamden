from unittest import TestCase
import asyncio
from cilantro_ee.protocol.overlay.kademlia.discovery import Discovery, DiscoveryServer
import zmq
import zmq.asyncio


class TestDiscovery(TestCase):
    def test_sync_request(self):
        ctx = zmq.asyncio.Context()

        async def recieve():
            socket = ctx.socket(zmq.ROUTER)
            socket.setsockopt(zmq.IDENTITY, b'X')
            socket.bind('inproc://testing')

            while True:
                event = await socket.poll(timeout=200, flags=zmq.POLLIN)
                if event:
                    break
            msg = await socket.recv_multipart()
            return msg

        async def request():
            d = Discovery(vk='3d9c09eab652e4b35dbf8b6baf588b4da3638a76a342734f9745d8fd517d24d0',
                          zmq_ctx=ctx,
                          url='inproc://abc')

            req = ctx.socket(zmq.ROUTER)
            req.connect('inproc://testing')

            await asyncio.sleep(0.1)

            res = await d.request(req, b'X')

            return res

        loop = asyncio.get_event_loop()
        tasks = asyncio.gather(recieve(), request())
        res = loop.run_until_complete(tasks)

        ctx.destroy()

        print(res)
        self.assertTrue(res)

    def test_reply(self):
        ctx = zmq.asyncio.Context()

        async def listen():
            await asyncio.sleep(0.1)
            socket = ctx.socket(zmq.ROUTER)
            socket.setsockopt(zmq.IDENTITY, b'X')
            socket.connect('inproc://abc')

            print('connected')

            print('sending')

            socket.send_multipart([b'a', b'b', b'c'])

            while True:
                event = await socket.poll(timeout=200, flags=zmq.POLLIN)
                if event:
                    break
            msg = await socket.recv_multipart()
            return msg

        async def reply():

            d = Discovery(vk='3d9c09eab652e4b35dbf8b6baf588b4da3638a76a342734f9745d8fd517d24d0',
                          zmq_ctx=ctx,
                          url='inproc://abc')

            d.is_listen_ready = True

            await asyncio.sleep(0.2)

            print('awaiting')
            res = await d.reply(b'X')

            return res

        loop = asyncio.get_event_loop()
        tasks = asyncio.gather(reply(), listen())
        res = loop.run_until_complete(tasks)

        ctx.destroy()

        print(res)
        self.assertTrue(res)

    def test_process_reply(self):
        ctx = zmq.asyncio.Context()

        async def req():
            socket = ctx.socket(zmq.ROUTER)
            socket.setsockopt(zmq.IDENTITY, b'X')
            socket.bind('inproc://testing')

            await asyncio.sleep(0.2)

            socket.send_multipart([b'a', b'b'])

        async def request():
            d = Discovery(vk='3d9c09eab652e4b35dbf8b6baf588b4da3638a76a342734f9745d8fd517d24d0',
                          zmq_ctx=ctx,
                          url='inproc://abc')

            await asyncio.sleep(0.1)

            req = ctx.socket(zmq.ROUTER)
            req.connect('inproc://testing')

            await asyncio.sleep(0.2)

            res = await d.try_process_reply(req, None)

            return res

        loop = asyncio.get_event_loop()
        tasks = asyncio.gather(req(), request())
        res = loop.run_until_complete(tasks)

        ctx.destroy()

        print(res)
        self.assertTrue(res)


def run_silent_loop(tasks):
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(tasks)
    except RuntimeError as e:
        pass


async def timeout_bomb(sleep=0.1):
    await asyncio.sleep(sleep)
    asyncio.get_event_loop().close()


class TestDiscoveryServer(TestCase):
    def test_init(self):
        DiscoveryServer('inproc://testing', 'blah', 'blah')

    def test_run_server(self):
        d = DiscoveryServer('inproc://testing', 'blah', 'blah')

        tasks = asyncio.gather(timeout_bomb(), d.serve())
        run_silent_loop(tasks)

        d.destroy()

    def test_send_message_to_discovery(self):
        ctx = zmq.asyncio.Context()

        address = 'inproc://testing2'

        d = DiscoveryServer(address, 'blah', 'blah', ctx=ctx)

        async def ping(msg, sleep):
            await asyncio.sleep(sleep)
            socket = ctx.socket(zmq.REQ)
            socket.connect(address)
            socket.send(msg)

            result = await socket.recv()
            self.assertEqual(msg, result)

        tasks = asyncio.gather(ping(b'999', 0.1), d.serve(), timeout_bomb(0.2))
        run_silent_loop(tasks)
        d.destroy()

