import unittest, asyncio, zmq, time, os, sys
from unittest import TestCase
from cilantro.protocol.overlay.interface import OverlayServer, OverlayClient
from cilantro.constants.testnet import TESTNET_MASTERNODES
from threading import Timer, Thread
from multiprocessing import Process, Queue

class TestInterface(TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['TEST_NAME'] = 'test'
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)

    def test_start_stop_service(self):
        def _stop():
            self.assertTrue(hasattr(self.server, 'dht'))
            self.assertTrue(self.server._started)
            self.server.teardown()
            self.assertIsInstance(self.server.cmd_sock, zmq.Socket)
            self.assertIsInstance(self.server.evt_sock, zmq.Socket)
            self.assertTrue(self.server.evt_sock.closed)
            self.server.loop.call_soon_threadsafe(self.server.loop.stop)

        self.server = OverlayServer(sk=TESTNET_MASTERNODES[0]['sk'], block=False)
        t = Timer(0.01, _stop)
        t.start()
        self.server.loop.run_forever()

    def test_send_commands(self):

        def _stop():
            self.client_proc.terminate()
            self.server.teardown()
            self.server.loop.call_soon_threadsafe(self.server.loop.stop)

        def _client_proc():
            time.sleep(0.01)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            def _send_cmd():
                asyncio.set_event_loop(loop)
                self.client.get_node_from_vk(TESTNET_MASTERNODES[0]['vk'])
            def _event_handler(e):
                self._test_res = e
            def _assert():
                self.assertEqual(self._test_res['ip'], '127.0.0.1')
                cli_t_cmd.join()
                self.client.teardown()
                loop.call_soon_threadsafe(loop.stop)

            self.client = OverlayClient(_event_handler, block=False)
            cli_t_cmd = Timer(0.2, _send_cmd)
            cli_t_cmd.start()
            cli_t_asrt = Timer(0.5, _assert)
            cli_t_asrt.start()
            self.client.loop.run_forever()

        self.server = OverlayServer(sk=TESTNET_MASTERNODES[0]['sk'], block=False)
        svr_t = Timer(3, _stop)
        svr_t.start()
        self.client_proc = Process(target=_client_proc)
        self.client_proc.start()
        self.server.loop.run_forever()
        self.assertEqual(self.client_proc.exitcode, 0)

    def test_send_commands_fail(self):

        def _stop():
            self.client_proc.terminate()
            self.server.teardown()
            self.server.loop.call_soon_threadsafe(self.server.loop.stop)

        def _client_proc():
            time.sleep(0.01)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            def _send_cmd():
                asyncio.set_event_loop(loop)
                self.client.get_node_from_vk('fsdfhsdfkjsdh')
            def _event_handler(e):
                self._test_res = e
            def _assert():
                self.assertTrue(self._test_res['event'], 'not_found')
                cli_t_cmd.join()
                self.client.teardown()
                loop.call_soon_threadsafe(loop.stop)

            self.client = OverlayClient(_event_handler, block=False)
            cli_t_cmd = Timer(0.2, _send_cmd)
            cli_t_cmd.start()
            cli_t_asrt = Timer(0.5, _assert)
            cli_t_asrt.start()
            self.client.loop.run_forever()

        self.server = OverlayServer(sk=TESTNET_MASTERNODES[0]['sk'], block=False)
        svr_t = Timer(3, _stop)
        svr_t.start()
        self.client_proc = Process(target=_client_proc)
        self.client_proc.start()
        self.server.loop.run_forever()
        self.assertEqual(self.client_proc.exitcode, 0)

    @classmethod
    def tearDownClass(cls):
        cls.loop.close()

if __name__ == '__main__':
    unittest.main()
