import unittest, asyncio, zmq, time, os
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
            time.sleep(0.05)
            p.terminate()
            OverlayInterface.cmd_sock.close()
            OverlayInterface._stop_service()

        def _send():
            def _e_handler(e):
                OverlayInterface._test_res = e
            def _thread():
                asyncio.set_event_loop(l)
                OverlayInterface.get_node_from_vk('82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144')
            def _assert():
                self.assertEqual(OverlayInterface._test_res['ip'], '127.0.0.1')
            l = asyncio.new_event_loop()
            asyncio.set_event_loop(l)
            asyncio.ensure_future(OverlayInterface.event_listener(_e_handler))
            th = Timer(0.01, _thread)
            th.start()
            th_a = Timer(0.03, _assert)
            th_a.start()
            l.run_forever()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        t = Timer(5, _stop)
        t.start()
        OverlayInterface._start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')

    def test_send_commands_fail(self):

        def _stop():
            p = Process(target=_send)
            p.start()
            time.sleep(0.05)
            p.terminate()
            OverlayInterface.cmd_sock.close()
            OverlayInterface._stop_service()

        def _send():
            def _e_handler(e):
                OverlayInterface._test_res = e
            def _thread():
                asyncio.set_event_loop(l)
                OverlayInterface.get_node_from_vk('askdjbaskdj')
            def _assert():
                self.assertEqual(OverlayInterface._test_res, {'status': 'not_found'})
            l = asyncio.new_event_loop()
            asyncio.set_event_loop(l)
            asyncio.ensure_future(OverlayInterface.event_listener(_e_handler))
            th = Timer(0.01, _thread)
            th.start()
            th_a = Timer(0.03, _assert)
            th_a.start()
            l.run_forever()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        t = Timer(5, _stop)
        t.start()
        OverlayInterface._start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')

    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()
