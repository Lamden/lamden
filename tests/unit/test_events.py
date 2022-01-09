from unittest import TestCase
from lamden.nodes.events import Event, EventListener, EventWriter, EventService
import shutil
import pathlib
import os

ROOT = pathlib.Path().cwd().joinpath('events')
SAMPLE_TOPIC = 'test'
SAMPLE_NUMBER = 101
SAMPLE_HASH = 'bb67232f70994134ed79'
SAMPLE_EVENT = Event(topics=[SAMPLE_TOPIC], number=SAMPLE_NUMBER, hash_str=SAMPLE_HASH)

class TestEvents(TestCase):
    def tearDown(self):
        try:
            shutil.rmtree(ROOT)
        except:
            pass

    def test_create_event(self):
        e = Event(topics=[SAMPLE_TOPIC], number=SAMPLE_NUMBER, hash_str=SAMPLE_HASH)

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
        self.assertTrue(SAMPLE_TOPIC in events[0].topics)
        self.assertEqual(events[0].data['number'], SAMPLE_NUMBER)
        self.assertEqual(events[0].data['hash'], SAMPLE_HASH)
