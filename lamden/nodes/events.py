'''
Events are things emitted across websockets that correspond with things that have occured in the system.

To create an event, a piece of data is written to a new file in events directory.

These events are consumed by a listener and sent across websockets to other computers who are listening to event updates

Directory scheme:

/events
--- event_1.e
--- event_2.e
'''
import pathlib
import uuid
from typing import List, Union
import os
import asyncio
import socketio
from sanic import Sanic
import json
import argparse

EVENTS_HOME = pathlib.Path().home().joinpath('.lamden').joinpath('events')
EXTENSION = '.e'

class Event:
    def __init__(self, topics: list, number: int, hash_str: str):
        self.topics = topics
        self.data = {}
        self.data['number'] = number
        self.data['hash'] = hash_str

class EventWriter:
    def __init__(self, root=EVENTS_HOME):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_event(self, event: Event):
        filename = str(uuid.uuid4()) + EXTENSION
        with open(self.root.joinpath(filename), 'w') as f:
            json.dump(event.__dict__, f)

class EventListener:
    def __init__(self, root=EVENTS_HOME):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def get_events(self) -> List[Event]:
        files = sorted(self.root.iterdir(), key=os.path.getmtime)
        events = []
        for file in files:
            with open(file, 'r') as f:
                try:
                    e = json.load(f)
                    event = Event(e['topics'], e['data']['number'], e['data']['hash'])
                    events.append(event)
                except:
                    # TODO(nikita): proper handling
                    print('failed to load event')
                os.remove(file)

        return events

class EventService:
    def __init__(self, port, listener_timeout=0.1,
                 logger=False, engineio_logger=False):
        self.port = port
        self.event_listener = EventListener()
        self.listener_timeout = listener_timeout
        self.sio = socketio.AsyncServer(async_mode='sanic', logger=logger, engineio_logger=engineio_logger)
        self.app = Sanic('event_service')
        self.sio.attach(self.app)
        self.__setup_sio_event_handlers()
        self.__register_app_listeners()

    def run(self):
        self.app.run(port=self.port)

    async def __gather_and_send_events(self):
        while True:
            await self.sio.sleep(self.listener_timeout)
            for event in self.event_listener.get_events():
                for topic in event.topics:
                    await self.sio.emit('event', event.data, room=topic)

    def __setup_sio_event_handlers(self):
        @self.sio.event
        async def join(sid, msg):
            self.sio.enter_room(sid, msg['room'])
            await self.sio.emit('message', {'action': 'joined_room', 'room': msg['room']}, room=sid)

        @self.sio.event
        async def leave(sid, msg):
            self.sio.leave_room(sid, msg['room'])
            await self.sio.emit('message', {'action': 'left_room', 'room': msg['room']}, room=sid)

    def __register_app_listeners(self):
        @self.app.listener('after_server_start')
        def __start_event_listener_task(app, loop):
            self.listener_task = self.sio.start_background_task(self.__gather_and_send_events)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, required=True)
    args = parser.parse_args()
    service = EventService(port=args.port, logger=True, engineio_logger=True)
    service.run()
