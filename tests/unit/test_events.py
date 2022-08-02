from unittest import TestCase
import unittest
from lamden.nodes.events import Event, EventListener, EventWriter, EventService
import shutil
import pathlib
import os
import socketio
import asyncio
from multiprocessing import Process
import time

ROOT = pathlib.Path().cwd().joinpath('events')
EVENT_SERVICE_PORT = 8000
SAMPLE_TOPIC = 'test'
SAMPLE_NUMBER = 101
SAMPLE_HASH = 'fcefe7743fa70c97ae2d5290fd673070da4b0293da095f0ae8aceccf5e62b6a1'
SAMPLE_DATA = {'number': SAMPLE_NUMBER, 'hash': SAMPLE_HASH}
SAMPLE_EVENT = Event(topics=[SAMPLE_TOPIC], data=SAMPLE_DATA)

TIMEOUT = 0.1

class TestEvents(TestCase):
    def tearDown(self):
        try:
            shutil.rmtree(ROOT)
        except:
            pass

    def test_create_event(self):
        e = Event(topics=[SAMPLE_TOPIC], data=SAMPLE_DATA)

        self.assertTrue(SAMPLE_TOPIC in e.topics)
        self.assertEqual(e.data['number'], SAMPLE_NUMBER)
        self.assertEqual(e.data['hash'], SAMPLE_HASH)

    def test_writer_creates_file(self):
        w = EventWriter(root=ROOT)
        w.write_event(SAMPLE_EVENT)

        self.assertEqual(len(list(ROOT.iterdir())), 1)

    def test_listener_sees_file_in_directory(self):
        w = EventWriter(root=ROOT)
        w.write_event(SAMPLE_EVENT)
        l = EventListener(root=ROOT)
        events = l.get_events()

        self.assertTrue(len(events), 1)

class MockSIOClient():
    def __init__(self):
        self.is_connected = False
        self.rooms = set()
        self.events = list()
        self.sio = socketio.AsyncClient()
        self.__register_sio_handlers()

    def __register_sio_handlers(self):
        @self.sio.event
        def connect():
            self.is_connected = True

        @self.sio.event
        def disconnect():
            self.is_connected = False

        @self.sio.event
        def message(data):
            if data['action'] == 'joined_room':
                self.rooms.add(data['room'])
            elif data['action'] == 'left_room':
                self.rooms.remove(data['room'])

        @self.sio.event
        def event(data):
            self.events.append(event)

class TestEventService(TestCase):
    service_process = None

    @classmethod
    def setUpClass(cls):
        TestEventService.service_process = Process(target=lambda: EventService(EVENT_SERVICE_PORT).run(), daemon=True)
        TestEventService.service_process.start()
        time.sleep(TIMEOUT)

    @classmethod
    def tearDownClass(cls):
        asyncio.get_event_loop().close()

    def setUp(self):
        self.client = MockSIOClient()
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.client.sio.connect(f'http://localhost:{EVENT_SERVICE_PORT}'))

    def tearDown(self):
        self.loop.run_until_complete(self.client.sio.disconnect())

    def test_service_is_reachable_by_clients(self):
        self.assertTrue(self.client.is_connected)

    def test_client_can_join_and_leave_room(self):
        self.loop.run_until_complete(self.client.sio.emit('join', {'room': SAMPLE_TOPIC}))
        self.loop.run_until_complete(asyncio.sleep(TIMEOUT))

        self.assertTrue(SAMPLE_TOPIC in self.client.rooms)

        self.loop.run_until_complete(self.client.sio.emit('leave', {'room': SAMPLE_TOPIC}))
        self.loop.run_until_complete(asyncio.sleep(TIMEOUT))

        self.assertFalse(SAMPLE_TOPIC in self.client.rooms)

    def test_service_doesnt_send_event_if_not_subscribed(self):
        EventWriter().write_event(SAMPLE_EVENT)
        self.loop.run_until_complete(asyncio.sleep(TIMEOUT))

        self.assertEqual(len(self.client.events), 0)

    def test_service_sends_event_if_subscribed(self):
        self.loop.run_until_complete(self.client.sio.emit('join', {'room': SAMPLE_TOPIC}))
        EventWriter().write_event(SAMPLE_EVENT)
        self.loop.run_until_complete(asyncio.sleep(TIMEOUT))

        self.assertEqual(len(self.client.events), 1)

