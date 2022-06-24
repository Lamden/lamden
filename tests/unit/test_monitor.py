from unittest import TestCase
from lamden.sockets.monitor import SocketMonitor

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

import zmq
import zmq.asyncio
from zmq.utils import monitor

class TestSocketMonitor(TestCase):
    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.ctx = zmq.asyncio.Context()

        self.monitor = SocketMonitor(socket_type="REQUEST")

    def tearDown(self) -> None:
        if self.monitor is not None:
            self.loop.run_until_complete(self.monitor.stop())

        self.ctx.destroy(linger=0)

        self.loop.stop()
        self.loop.close()
        self.loop = None

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_loop_creation(self):
        self.assertIsNotNone(self.loop)

    def test_INSTANCE__SocketMonitor(self):
        self.assertIsInstance(self.monitor, SocketMonitor)

    def test_METHOD_start__can_start_task(self):
        self.assertFalse(self.monitor.running)
        self.assertTrue(self.monitor.check_for_events_task_stopped)

        self.monitor.start()
        self.async_sleep(1)

        self.assertTrue(self.monitor.running)
        self.assertFalse(self.monitor.check_for_events_task_stopped)

    def test_METHOD_stop__can_stop_monitor(self):
        self.assertFalse(self.monitor.running)
        self.assertTrue(self.monitor.check_for_events_task_stopped)

        self.monitor.start()
        self.async_sleep(1)

        self.assertTrue(self.monitor.running)
        self.assertFalse(self.monitor.check_for_events_task_stopped)

        self.loop.run_until_complete(self.monitor.stop())

        self.assertFalse(self.monitor.running)
        self.assertTrue(self.monitor.check_for_events_task_stopped)

    def test_METHOD_monitor__can_add_socket_pair_to_sockets_to_monitor(self):
        self.assertEqual(0, len(self.monitor.sockets_to_monitor))

        req = self.ctx.socket(zmq.REQ)
        pair_socket = req.get_monitor_socket()

        self.monitor.monitor(socket=req)

        self.assertEqual(1, len(self.monitor.sockets_to_monitor))

        sockets = self.monitor.sockets_to_monitor

        self.assertTrue(pair_socket in sockets)


    def test_METHOD_check_for_events__can_receive_events_from_socket(self):
        self.monitor.start()

        req = self.ctx.socket(zmq.REQ)

        self.monitor.monitor(socket=req)

        req.connect('tcp://127.0.0.1:19000')

        self.async_sleep(1)



