import unittest, asyncio, zmq, time
from unittest import TestCase
from cilantro.protocol.overlay.interface import OverlayInterface
from threading import Timer, Thread
from multiprocessing import Process

class TestInterface(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_start_stop_service(self):
        def _stop():
            self.assertTrue(hasattr(OverlayInterface, 'dht'))
            OverlayInterface._stop_service()
            self.assertTrue(OverlayInterface.event_sock.closed)
            self.assertIsInstance(OverlayInterface.cmd_sock, zmq.Socket)
            self.assertIsInstance(OverlayInterface.event_sock, zmq.Socket)

        t = Timer(5, _stop)
        t.start()
        OverlayInterface._start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')

    def test_overlay_command_socket(self):
        OverlayInterface._overlay_command_socket()
        self.assertIsInstance(OverlayInterface.cmd_sock, zmq.Socket)

    def test_send_commands(self):

        def _stop():
            p = Process(target=_send)
            p.start()
            time.sleep(0.1)
            p.terminate()
            OverlayInterface.cmd_sock.close()
            OverlayInterface._stop_service()

        def _send():
            print('!!!s')
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            def _e_handler(e):
                print('!!!',e)
            OverlayInterface.listen_for_events(_e_handler)

            # def _thread():
            #     loop = asyncio.new_event_loop()
            #     asyncio.set_event_loop(loop)
            #     OverlayInterface.get_node_from_vk('askdjbaskdj')
            # loop = asyncio.new_event_loop()
            # asyncio.set_event_loop(loop)
            # asyncio.ensure_future(OverlayInterface.event_listener(_e_handler))
            # t = Thread(target=_thread)
            # t.start()
            # loop.run_forever()

        t = Timer(5, _stop)
        t.start()
        OverlayInterface._start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')

    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()
