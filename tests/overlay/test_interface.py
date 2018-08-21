import unittest, asyncio
from unittest import TestCase
from cilantro.protocol.overlay.interface import OverlayInterface
from threading import Timer

class TestInterface(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_start_stop_service(self):
        OverlayInterface.start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')
        self.assertTrue(hasattr(OverlayInterface, 'dht'))
        OverlayInterface.stop_service()
        self.assertTrue(OverlayInterface.event_sock.closed)

    def test_overlay_event_socket(self):
        OverlayInterface.start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')
        OverlayInterface.overlay_event_socket()

    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()
