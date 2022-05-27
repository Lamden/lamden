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

        self.ctx = zmq.Context.instance()

        self.monitor = SocketMonitor()

    def tearDown(self) -> None:
        if self.monitor is not None:
            self.loop.run_until_complete(self.monitor.stop())
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

    def test_monitoring_with_poller(self):
        poller = zmq.asyncio.Poller()
        ctx = zmq.Context()
        """Test connected monitoring socket."""
        s_rep = ctx.socket(zmq.REP)
        s_req = ctx.socket(zmq.REQ)

        poller.register(s_rep, zmq.POLLIN)

        s_req.bind("tcp://127.0.0.1:6667")
        # try monitoring the REP socket
        # create listening socket for monitor
        s_event = s_rep.get_monitor_socket()
        s_event.linger = 0

        # test receive event for connect event
        s_rep.connect("tcp://127.0.0.1:6667")
        m = monitor.recv_monitor_message(s_event)
        if m['event'] == zmq.EVENT_CONNECT_DELAYED:
            self.assertEqual(m['endpoint'], b"tcp://127.0.0.1:6667")
            # test receive event for connected event
            m = monitor.recv_monitor_message(s_event)
        self.assertEqual(m['event'], zmq.EVENT_CONNECTED)
        self.assertEqual(m['endpoint'], b"tcp://127.0.0.1:6667")

        s_req.send_string("Hello")

        task = self.loop.run_until_complete(poller.poll(timeout=1000))

        self.assertEqual(1, len(task))
        for socket in task:
            msg = socket[0].recv()
            self.assertEqual('Hello', msg.decode('UTF-8'))




