from unittest import TestCase
import asyncio
from cilantro_ee.protocol.overlay.kademlia.discovery import Discovery
import zmq


class TestDiscovery(TestCase):

    def async_test(f):
        def wrapper(*args, **kwargs):
            coro = asyncio.coroutine(f)
            future = coro(*args, **kwargs)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(future)

        return wrapper

    @async_test
    def test_init(self):
        d = Discovery(vk='3d9c09eab652e4b35dbf8b6baf588b4da3638a76a342734f9745d8fd517d24d0',
                      zmq_ctx=zmq.Context())