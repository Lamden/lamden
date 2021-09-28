from unittest import TestCase
from lamden.nodes.events import Event, EventListener, EventWriter, Connection, ConnectionManager
import pathlib
import os
import shutil
import asyncio
import websockets
import json


ROOT = pathlib.Path().cwd().joinpath('events')


class MockWebsocket:
    def __init__(self, remote_address):
        self.remote_address = remote_address
        self.messages = []
        self.input = []

    async def send(self, msg):
        self.messages.append(msg)

    async def close(self):
        return

    async def recv(self):
        return self.input.pop(0)

    async def __aiter__(self):
        try:
            while True:
                yield await self.recv()
        except:
            return


class BadMockWebSocket:
    def __init__(self, remote_address):
        self.remote_address = remote_address
        self.messages = []

    async def send(self, msg):
        raise websockets.WebSocketProtocolError

    async def close(self):
        return


class TestEvents(TestCase):
    def tearDown(self):
        try:
            shutil.rmtree(ROOT)
        except:
            pass

    def test_create_event(self):
        e = Event(name='test', payload='thing')
        self.assertEqual(e.name, 'test')
        self.assertEqual(e.payload, 'thing')

    def test_writer_creates_file(self):
        w = EventWriter(root=ROOT)
        w.write_event('test', b'thing')

        self.assertTrue(os.path.isdir(ROOT.joinpath('test')))
        self.assertEqual(len(list(ROOT.joinpath('test').iterdir())), 1)

    def test_listener_sees_file_in_directory(self):
        w = EventWriter(root=ROOT)
        w.write_event('test', b'thing')

        l = EventListener(root=ROOT)
        events = l._get_events_for_directory(ROOT.joinpath('test'))

        self.assertTrue(len(events), 1)
        self.assertEqual(events[0].name, 'test')
        self.assertEqual(events[0].payload, b'thing')

    def test_listener_deletes_directory(self):
        w = EventWriter(root=ROOT)
        w.write_event('test', b'thing')

        self.assertTrue(os.path.isdir(ROOT.joinpath('test')))

        l = EventListener(root=ROOT)
        l._get_events_for_directory(ROOT.joinpath('test'))

        self.assertFalse(os.path.isdir(ROOT.joinpath('test')))

    def test_listener_multiple_events_single_topic(self):
        w = EventWriter(root=ROOT)
        w.write_event('test', b'thing1')
        w.write_event('test', b'thing2')

        l = EventListener(root=ROOT)
        events = l._get_events_for_directory(ROOT.joinpath('test'))

        self.assertTrue(len(events), 2)
        self.assertEqual(events[0].name, 'test')
        self.assertEqual(events[0].payload, b'thing1')
        self.assertEqual(events[1].name, 'test')
        self.assertEqual(events[1].payload, b'thing2')

    def test_listener_multiple_events_multiple_topics(self):
        w = EventWriter(root=ROOT)
        w.write_event('test1', b'thing1')
        w.write_event('test2', b'thing2')

        l = EventListener(root=ROOT)
        events = l.get_events()

        self.assertTrue(len(events), 2)
        self.assertEqual(events[0].name, 'test1')
        self.assertEqual(events[0].payload, b'thing1')
        self.assertEqual(events[1].name, 'test2')
        self.assertEqual(events[1].payload, b'thing2')

    def test_subscribe_new_socket_new_topic(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        cm.subscribe(socket, topic='test_topic')

        self.assertEqual(cm.connections['test'].websocket, socket)
        self.assertEqual(cm.connections['test'].subscriptions, 1)

        self.assertEqual(cm.subscriptions['test_topic'], {'test'})

    def test_subscription_same_socket_another_topic(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        cm.subscribe(socket, topic='test_topic')
        cm.subscribe(socket, topic='test_topic2')

        self.assertEqual(cm.connections['test'].websocket, socket)
        self.assertEqual(cm.connections['test'].subscriptions, 2)

        self.assertEqual(cm.subscriptions['test_topic'], {'test'})
        self.assertEqual(cm.subscriptions['test_topic2'], {'test'})

    def test_subscription_multiple_sockets_same_topic(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        cm.subscribe(socket, topic='test_topic')

        self.assertEqual(cm.connections['test'].websocket, socket)
        self.assertEqual(cm.connections['test'].subscriptions, 1)

        socket2 = MockWebsocket('test2')
        cm.subscribe(socket2, topic='test_topic')

        self.assertEqual(cm.subscriptions['test_topic'], {'test', 'test2'})

    def test_unsubscription_if_not_exist_has_no_effect(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        cm.unsubscribe(socket, 'topic')

    def test_unsubscribe_single_node_single_topic(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        cm.subscribe(socket, topic='test_topic')

        loop = asyncio.get_event_loop()

        loop.run_until_complete(cm.unsubscribe(socket, 'test_topic'))

        self.assertEqual(cm.connections, {})
        self.assertEqual(len(cm.subscriptions), 0)

    def test_unsubscribe_single_node_multiple_topics_only_removes_topic(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        cm.subscribe(socket, topic='test_topic')
        cm.subscribe(socket, topic='test_topic2')

        loop = asyncio.get_event_loop()
        loop.run_until_complete(cm.unsubscribe(socket, 'test_topic'))

        self.assertEqual(cm.connections['test'].websocket, socket)
        self.assertEqual(cm.subscriptions['test_topic2'], {'test'})
        self.assertEqual(len(cm.subscriptions), 1)

    def test_unsubscribe_multiple_sockets_multiple_topics(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        socket2 = MockWebsocket('test2')

        cm.subscribe(socket, topic='test_topic')
        cm.subscribe(socket, topic='test_topic2')

        cm.subscribe(socket2, topic='test_topic')
        cm.subscribe(socket2, topic='test_topic2')

        loop = asyncio.get_event_loop()
        loop.run_until_complete(cm.unsubscribe(socket, 'test_topic'))

        self.assertEqual(cm.connections['test'].websocket, socket)
        self.assertEqual(cm.connections['test2'].websocket, socket2)

        self.assertEqual(cm.connections['test'].subscriptions, 1)
        self.assertEqual(cm.connections['test2'].subscriptions, 2)

        self.assertEqual(cm.subscriptions['test_topic2'], {'test', 'test2'})
        self.assertEqual(cm.subscriptions['test_topic'], {'test2'})

    def test_websocket_send_message_mock(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')

        loop = asyncio.get_event_loop()
        loop.run_until_complete(cm.send_message(socket, 'yo'))
        loop.run_until_complete(cm.send_message(socket, 'yo2'))

        self.assertEqual(socket.messages, ['yo', 'yo2'])

    def test_websocket_send_message_failure_mock_no_connections(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = BadMockWebSocket('test')

        loop = asyncio.get_event_loop()
        loop.run_until_complete(cm.send_message(socket, 'yo'))

    def test_purge_connection_removes_all_subscriptions_and_connection(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')

        cm.subscribe(socket, topic='test_topic')
        cm.subscribe(socket, topic='test_topic1')
        cm.subscribe(socket, topic='test_topic2')
        cm.subscribe(socket, topic='test_topic3')
        cm.subscribe(socket, topic='test_topic4')
        cm.subscribe(socket, topic='test_topic5')
        cm.subscribe(socket, topic='test_topic6')
        cm.subscribe(socket, topic='test_topic7')
        cm.subscribe(socket, topic='test_topic8')
        cm.subscribe(socket, topic='test_topic9')

        self.assertEqual(cm.connections['test'].subscriptions, 10)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(cm.purge_connection('test'))

        self.assertEqual(len(cm.subscriptions), 0)

    def test_purge_connection_multiple_sockets(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')

        cm.subscribe(socket, topic='test_topic')
        cm.subscribe(socket, topic='test_topic1')
        cm.subscribe(socket, topic='test_topic2')
        cm.subscribe(socket, topic='test_topic3')
        cm.subscribe(socket, topic='test_topic4')
        cm.subscribe(socket, topic='test_topic5')
        cm.subscribe(socket, topic='test_topic6')
        cm.subscribe(socket, topic='test_topic7')
        cm.subscribe(socket, topic='test_topic8')
        cm.subscribe(socket, topic='test_topic9')

        socket2 = MockWebsocket('test2')

        cm.subscribe(socket2, topic='test_topic')
        cm.subscribe(socket2, topic='test_topic1')
        cm.subscribe(socket2, topic='test_topic2')
        cm.subscribe(socket2, topic='test_topic3')
        cm.subscribe(socket2, topic='test_topic4')
        cm.subscribe(socket2, topic='test_topic5')
        cm.subscribe(socket2, topic='test_topic6')
        cm.subscribe(socket2, topic='test_topic7')
        cm.subscribe(socket2, topic='test_topic8')
        cm.subscribe(socket2, topic='test_topic9')

        self.assertEqual(cm.connections['test'].subscriptions, 10)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(cm.purge_connection('test'))

        self.assertEqual(len(cm.subscriptions), 10)

    def test_subscribe_twice_does_not_add_two_connections(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')

        cm.subscribe(socket, topic='test_topic')
        cm.subscribe(socket, topic='test_topic')

        self.assertEqual(cm.connections['test'].subscriptions, 1)

    def test_serve_subscribes(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        socket.input.append(json.dumps({
            'action': 'subscribe',
            'topic': 'test_topic'
        }))

        loop = asyncio.get_event_loop()
        loop.run_until_complete(cm.serve(socket, '/'))

        self.assertEqual(cm.connections['test'].websocket, socket)
        self.assertEqual(cm.connections['test'].subscriptions, 1)

        self.assertEqual(cm.subscriptions['test_topic'], {'test'})

    def test_serve_unsubscribe(self):
        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        socket.input.append(json.dumps({
            'action': 'subscribe',
            'topic': 'test_topic'
        }))
        socket.input.append(json.dumps({
            'action': 'unsubscribe',
            'topic': 'test_topic'
        }))

        loop = asyncio.get_event_loop()
        loop.run_until_complete(cm.serve(socket, '/'))

        self.assertEqual(cm.connections, {})
        self.assertEqual(len(cm.subscriptions), 0)

    def test_process_events_returns_if_subscribed(self):
        w = EventWriter(root=ROOT)
        w.write_event('test_topic', b'thing')

        l = EventListener(root=ROOT)
        cm = ConnectionManager(listener=l)

        socket = MockWebsocket('test')
        socket.input.append(json.dumps({
            'action': 'subscribe',
            'topic': 'test_topic'
        }))

        loop = asyncio.get_event_loop()
        loop.run_until_complete(cm.serve(socket, '/'))

        loop.run_until_complete(cm.process_events())

        self.assertEqual(socket.messages, [b'thing'])
