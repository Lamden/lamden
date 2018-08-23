import unittest, asyncio, zmq, time, os, sys
from unittest import TestCase
from cilantro.protocol.overlay.interface import OverlayInterface
from threading import Timer, Thread
from multiprocessing import Process, Queue

class TestInterface(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)

    def test_start_stop_service(self):
        def _stop():
            self.assertTrue(hasattr(OverlayInterface, 'dht'))
            OverlayInterface._stop_service()
            self.assertTrue(OverlayInterface.event_sock.closed)
            self.assertIsInstance(OverlayInterface.cmd_sock, zmq.Socket)
            self.assertIsInstance(OverlayInterface.event_sock, zmq.Socket)
            OverlayInterface.loop.call_soon_threadsafe(OverlayInterface.loop.stop)

        t = Timer(5, _stop)
        t.start()
        OverlayInterface._start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')

    def test_send_commands(self):

        def _stop():
            p.start()
            time.sleep(0.1)
            p.terminate()
            OverlayInterface._stop_service()
            OverlayInterface.loop.call_soon_threadsafe(OverlayInterface.loop.stop)

        def _send_msg():
            def _e_handler(e):
                OverlayInterface._test_res = e
            def _thread():
                asyncio.set_event_loop(l)
                OverlayInterface.get_node_from_vk('82540bb5a9c84162214c5540d6e43be49bbfe19cf49685660cab608998a65144')
            def _assert():
                self.assertEqual(OverlayInterface._test_res['ip'], '127.0.0.1')
                l.call_soon_threadsafe(l.stop)
                th.join()
                th_a.join()

            l = asyncio.new_event_loop()
            asyncio.set_event_loop(l)
            asyncio.ensure_future(OverlayInterface.event_listener(_e_handler))
            th = Timer(0.01, _thread)
            th.start()
            th_a = Timer(0.05, _assert)
            th_a.start()
            l.run_forever()

        p = Process(target=_send_msg)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        t = Timer(5, _stop)
        t.start()
        OverlayInterface._start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')
        self.assertEqual(p.exitcode, 0)

    def test_send_commands_fail(self):

        def _stop():
            p.start()
            time.sleep(0.1)
            p.terminate()
            OverlayInterface._stop_service()
            OverlayInterface.loop.call_soon_threadsafe(OverlayInterface.loop.stop)

        def _send_msg():
            def _e_handler(e):
                OverlayInterface._test_res = e
            def _thread():
                asyncio.set_event_loop(l)
                OverlayInterface.get_node_from_vk('fsdfhsdfkjsdh')
            def _assert():
                self.assertTrue(OverlayInterface._test_res['event'], 'not_found')
                l.call_soon_threadsafe(l.stop)
                th.join()
                th_a.join()

            l = asyncio.new_event_loop()
            asyncio.set_event_loop(l)
            asyncio.ensure_future(OverlayInterface.event_listener(_e_handler))
            th = Timer(0.01, _thread)
            th.start()
            th_a = Timer(0.05, _assert)
            th_a.start()
            l.run_forever()

        p = Process(target=_send_msg)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        t = Timer(5, _stop)
        t.start()
        OverlayInterface._start_service(sk='06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')
        self.assertEqual(p.exitcode, 0)

    @classmethod
    def tearDownClass(cls):
        cls.loop.close()

if __name__ == '__main__':
    unittest.main()
