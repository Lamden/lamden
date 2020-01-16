from unittest import TestCase
from cilantro_ee.services.overlay.client import OverlayClient
import zmq
import zmq.asyncio
import asyncio


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestOverlayClient(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_sub_socket_receives_events(self):
        def reply_callback(*args, **kwargs):
            pass

        l = []

        def event_callback(*args, **kwargs):
            l.append('got event!')

        async def send_event():
            self.evt_sock.send_json({'hello': 'there'})

        o = OverlayClient(reply_callback, event_callback, self.ctx)

        self.evt_sock = self.ctx.socket(socket_type=zmq.PUB)
        self.evt_sock.bind('tcp://127.0.0.1:10003')

        tasks = asyncio.gather(
            o.start(),
            send_event(),
            stop_server(o, 0.1)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)
