'''
Events are things emitted across websockets that correspond with things that have occured in the system.

To create an event, a piece of data is written to a new file in a directory. This directory is the 'event name'. The
file is the payload.

These events are consumed by a listener and sent across websockets to other computers who are listening to event updates

Directory scheme:

/events
--- event_name
--- --- event_1
--- event_name_2
--- --- <empty>
'''
import pathlib
import uuid
from typing import List
import os

EVENTS_HOME = pathlib.Path().home().joinpath('.lamden').joinpath('events')
EXTENSION = '.e'


class Event:
    def __init__(self, name, payload):
        self.name = name
        self.payload = payload


class EventWriter:
    def __init__(self, root=EVENTS_HOME):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_event(self, event_name, payload):
        dir_ = self.root.joinpath(event_name)
        dir_.mkdir(parents=True, exist_ok=True)

        name = str(uuid.uuid4()) + EXTENSION
        with open(dir_.joinpath(name), 'wb') as f:
            f.write(payload)


class EventListener:
    def __init__(self, root=EVENTS_HOME, poll=250):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

        self.poll = poll / 1_000 # convert to milliseconds

    def get_events(self) -> List[Event]:
        dirs = sorted(self.root.iterdir(), key=os.path.getmtime)

        events = []

        for d in dirs:
            _events = self._get_events_for_directory(d)
            events.extend(_events)

        return events

    @staticmethod
    def _get_events_for_directory(directory: pathlib.Path):
        files = sorted(directory.iterdir(), key=os.path.getmtime)

        events = []
        for file in files:
            with open(file) as f:
                payload = f.read()

            os.remove(file)

            e = Event(name=directory, payload=payload)
            events.append(e)

        os.removedirs(directory)

        return events
