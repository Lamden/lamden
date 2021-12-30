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
from typing import List, Union
import os
from collections import defaultdict
import websockets
import asyncio
import json

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
    def __init__(self, root=EVENTS_HOME):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def get_events(self) -> List[Event]:
        dirs = sorted(self.root.iterdir() if self.root.is_dir() else [], key=os.path.getmtime)

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
            with open(file, 'rb') as f:
                payload = f.read()

            os.remove(file)

            e = Event(name=directory.parts[-1], payload=payload)
            events.append(e)

        os.removedirs(directory)

        return events


class Connection:
    def __init__(self, websocket):
        self.websocket = websocket
        self.subscriptions = 1


class ConnectionManager:
    def __init__(self, listener: EventListener):
        self.subscriptions = defaultdict(set)
        self.connections = {}

        self.listener = listener
        self.running = False

    async def serve(self, websocket: websockets.WebSocketServerProtocol, path):
        if path != '/':
            await websocket.close()
            return

        async for message in websocket:
            try:
                m = json.loads(message)
            except:
                continue
            action = m.get('action')
            topic = m.get('topic')

            if action == 'subscribe':
                self.subscribe(websocket, topic)
            elif action == 'unsubscribe':
                await self.unsubscribe(websocket, topic)

    def subscribe(self, websocket, topic):
        current_connection = self.connections.get(websocket.remote_address)

        # If it is a new connection, create a connection object and store it
        if current_connection is None:
            self.connections[websocket.remote_address] = Connection(websocket)
        # Otherwise, modify the currently stored connection
        elif websocket.remote_address not in self.subscriptions[topic]:
            current_connection.subscriptions += 1

        self.subscriptions[topic].add(websocket.remote_address)

    async def unsubscribe(self, websocket, topic):
        current_connection = self.connections.get(websocket.remote_address)

        # If the current connection doesn't exist, nothing to unsubscribe from
        if current_connection is None:
            return
        # Otherwise, deduct 1 from the subscriptions. If it is the last subscription, close the socket
        else:
            current_connection.subscriptions -= 1
            if current_connection.subscriptions == 0:
                del self.connections[websocket.remote_address]

        # Remove the topic from the subscriptions
        self.subscriptions[topic].remove(websocket.remote_address)

        # Clean up topics that have no subscribers
        if len(self.subscriptions[topic]) == 0:
            del self.subscriptions[topic]

    async def send_message(self, websocket: websockets.WebSocketServerProtocol, message):
        try:
            await websocket.send(message)
        except websockets.WebSocketProtocolError:
            await self.purge_connection(websocket.remote_address)
        except websockets.exceptions.ConnectionClosedOK:
            await self.purge_connection(websocket.remote_address)

    async def purge_connection(self, address):
        to_remove = []
        for topic, connections in self.subscriptions.items():
            connections.remove(address)
            if len(connections) == 0:
                to_remove.append(topic)

        for r in to_remove:
            del self.subscriptions[r]

        try:
            self.connections.pop(address)
            await self.connections[address].close()
        except:
            return

    async def process_events(self):
        events = self.listener.get_events()
        for event in events:
            subscribers = self.subscriptions[event.name]
            coroutines = [self.send_message(self.connections[w].websocket, event.payload) for w in subscribers]
            await asyncio.gather(*coroutines)


class WebsocketServer(ConnectionManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Explicit topics are not able to be split into parts
        # Wildcard topics are split into parts and have a * to denote
        self.explicit_topics = set()
        self.wildcard_topics = set()

    def is_valid_topic(self, topic):
        return True

    def add_topic(self, topic):
        pass
