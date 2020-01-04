from unittest import TestCase
from unittest.mock import MagicMock

import zmq, zmq.asyncio
from cilantro_ee.core.sockets.lsocket import *
from cilantro_ee.core.sockets.socket_manager import *
from cilantro_ee.crypto import wallet
from cilantro_ee.messages.base.base_signal import SignalBase


def _build_mock_manager():
    manager = MagicMock(spec=SocketManager)
    manager.signing_key, manager.verifying_key = wallet.new()
    manager.overlay_client = MagicMock()
    manager.overlay_client.get_ip_from_vk = MagicMock(side_effect=list(range(100)))
    manager.pending_lookups = {}
    return manager


def _build_lsocket(socket_type=None, secure=False, domain='*'):
    if socket_type is None:
        return LSocketBase(socket=MagicMock(), manager=_build_mock_manager(), secure=secure, domain=domain)
    elif socket_type is zmq.ROUTER:
        # TODO implement
        pass


class SignalTestMessage(SignalBase): pass  # Just a message type used for testing in these tests


class TestLSocketBase(TestCase):

    def test_connect_with_vk_lookup(self):
        vk = 'A' * 64
        sock = _build_lsocket()

        sock.connect(port=9999, vk=vk)

        self.assertTrue(0 in sock.pending_lookups)
        self.assertTrue(vk in sock.conn_tracker)
        self.assertEqual(sock.conn_tracker[vk], ('connect', (), {'port': 9999, 'vk': vk}))
        self.assertTrue(0 in sock.manager.pending_lookups)
        self.assertEqual(sock.manager.pending_lookups[0], sock)

    def test_connect_with_vk_lookup_then_got_ip(self):
        vk, ip = 'A' * 64, '135.215.96.143'
        event = {'event_id': 0, 'event': 'got_ip', 'vk': vk, 'ip': ip}
        sock = _build_lsocket()
        sock.connect(port=9999, vk=vk)

        sock.handle_overlay_event(event)

        expected_url = "tcp://{}:9999".format(ip)
        actual_url = sock.socket.connect.call_args[0][0]
        self.assertEqual(expected_url, actual_url)

    def test_bind_with_vk_lookup_then_got_ip(self):
        vk, ip = 'A' * 64, '135.215.96.143'
        event = {'event_id': 0, 'event': 'got_ip', 'vk': vk, 'ip': ip}
        sock = _build_lsocket()
        sock.bind(port=9999, vk=vk)

        sock.handle_overlay_event(event)

        expected_url = "tcp://{}:9999".format(ip)
        actual_url = sock.socket.bind.call_args[0][0]
        self.assertEqual(expected_url, actual_url)

    def test_bind_with_vk_lookup(self):
        vk = 'A' * 64
        sock = _build_lsocket()

        sock.bind(port=9999, vk=vk)

        self.assertTrue(0 in sock.pending_lookups)
        self.assertTrue(vk in sock.conn_tracker)
        self.assertEqual(sock.conn_tracker[vk], ('bind', (), {'port': 9999, 'vk': vk}))
        self.assertTrue(0 in sock.manager.pending_lookups)
        self.assertEqual(sock.manager.pending_lookups[0], sock)

    def test_getattr_with_lsocket_attr(self):
        sock = _build_lsocket()

        attr = sock.pending_lookups
        self.assertEqual(attr, sock.pending_lookups)

    def test_getattr_with_sock_attr(self):
        sock = _build_lsocket()

        attr = sock.routing_id
        self.assertEqual(attr, sock.socket.routing_id)

    def test_connect_with_vk_lookup_then_node_online(self):
        vk, ip = 'A' * 64, '135.215.96.143'
        got_ip = {'event_id': 0, 'event': 'got_ip', 'vk': vk, 'ip': ip}
        node_online = {'event_id': 1, 'event': 'node_online', 'vk': vk, 'ip': ip}
        sock = _build_lsocket()

        sock.connect(port=9999, vk=vk)
        sock.handle_overlay_event(got_ip)
        sock.handle_overlay_event(node_online)

        self.assertEqual(len(sock.socket.connect.call_args_list), 2)
        self.assertEqual(sock.socket.connect.call_args_list[0], sock.socket.connect.call_args_list[1])

    def test_bind_with_vk_lookup_then_node_online(self):
        vk, ip = 'A' * 64, '135.215.96.143'
        got_ip = {'event_id': 0, 'event': 'got_ip', 'vk': vk, 'ip': ip}
        node_online = {'event_id': 1, 'event': 'node_online', 'vk': vk, 'ip': ip}
        sock = _build_lsocket()

        sock.bind(port=9999, vk=vk)
        sock.handle_overlay_event(got_ip)
        sock.handle_overlay_event(node_online)

        self.assertEqual(len(sock.socket.bind.call_args_list), 2)
        self.assertEqual(sock.socket.bind.call_args_list[0], sock.socket.bind.call_args_list[1])

