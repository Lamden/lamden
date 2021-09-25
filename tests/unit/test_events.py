from unittest import TestCase
from lamden.nodes.events import Event, EventListener, EventWriter
import pathlib
import os
import shutil

ROOT = pathlib.Path().cwd().joinpath('events')


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
