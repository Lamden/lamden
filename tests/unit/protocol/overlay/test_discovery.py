from unittest import TestCase
import asyncio
from cilantro_ee.protocol.overlay.kademlia.discovery import Discovery
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

            await asyncio.sleep(1)

            res = await d.request(req, b'X')

            return res

        loop = asyncio.get_event_loop()
        tasks = asyncio.gather(recieve(), request())
        res = loop.run_until_complete(tasks)

        ctx.destroy()

        print(res)
        self.assertTrue(res)


    def test_request_fails_zmq_not_reachable(self):
        async def test():
            d = Discovery(vk='3d9c09eab652e4b35dbf8b6baf588b4da3638a76a342734f9745d8fd517d24d0',
                          zmq_ctx=zmq.Context(),
                          url='inproc://testing',
                          is_debug=True)

            socket = zmq.Context().socket(zmq.ROUTER)
            socket.setsockopt(zmq.IDENTITY, b'x')
            socket.bind('inproc://testing')

            res = await d.request(socket, b'x')

            print(await socket.recv_multipart())

            return res

        loop = asyncio.get_event_loop()

        res = loop.run_until_complete(test())
        self.assertFalse(res)