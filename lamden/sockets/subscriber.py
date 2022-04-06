import asyncio
import zmq
import zmq.asyncio

from lamden.logger.base import get_logger

from typing import Callable

EXCEPTION_TOPIC_NOT_STRING = "Topic must be string."
EXCEPTION_NO_SOCKET = "No socket created."

class Subscriber():
    def __init__(self, address: str, callback: Callable = None, logger=None, topics: list=[]):
        self.log = logger or get_logger("SUBSCRIBER")

        self.running = False

        self.address = address
        self.callback = callback
        self.topics = list(topics)

        self.ctx = zmq.asyncio.Context().instance()

        self.loop = None
        self.socket = None

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def socket_is_bound(self) -> bool:
        try:
            return len(self.socket.LAST_ENDPOINT) > 0
        except Exception as err:
            return False

    @property
    def socket_is_closed(self) -> bool:
        try:
            return self.socket.closed
        except AttributeError:
            return True

    def setup_event_loop(self) -> None:
        try:
            self.loop = asyncio.get_event_loop()
            if self.loop._closed:
                raise AttributeError
        except Exception:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def create_socket(self) -> None:
        self.socket = self.ctx.socket(zmq.SUB)

    def connect_socket(self) -> None:
        if not self.socket:
            self.create_socket()
        self.socket.bind(self.address)

    def subscribe_to_topics(self) -> None:
        if not self.socket:
            raise AttributeError(EXCEPTION_NO_SOCKET)

        for topic in self.topics:
            if not isinstance(topic, str):
                raise TypeError(EXCEPTION_TOPIC_NOT_STRING)

            self.socket.setsockopt(zmq.SUBSCRIBE, topic.encode('UTF-8'))

        # re-poll to update publisher with our new topics
        if self.running:
            asyncio.ensure_future(self.messages_waiting())

    def add_topic(self, topic: str) -> None:
        if not isinstance(topic, str):
            raise TypeError(EXCEPTION_TOPIC_NOT_STRING)

        self.topics.append(topic)

        if self.socket:
            self.socket.setsockopt(zmq.SUBSCRIBE, topic.encode('UTF-8'))
        if self.running:
            asyncio.ensure_future(self.messages_waiting())

    def start(self) -> None:
        self.create_socket()
        self.subscribe_to_topics()
        self.connect_socket()
        self.setup_event_loop()

        asyncio.ensure_future(self.check_for_messages())

        self.log.info('[SUBSCRIBER] Running...')
        print(f'[{self.log.name}][SUBSCRIBER] Running...')

    async def messages_waiting(self, timeout: int = 1) -> bool:
        return await self.socket.poll(timeout=timeout) > 0

    async def check_for_messages(self) -> None:
        self.running = True

        # initial poll to contact publisher
        await self.messages_waiting()

        while self.running:
            if await self.messages_waiting(timeout=50):
                data = await self.socket.recv_multipart()

                self.log.info(f'[SUBSCRIBER] Got event from {self.address}')
                print(f'[{self.log.name}][SUBSCRIBER] Got event from {self.address}')

                if self.callback:
                    self.callback(data)

    def close_socket(self) -> None:
        if self.socket_is_closed:
            return

        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.close()

    async def stopping(self) -> None:
        while not self.socket_is_closed:
            await asyncio.sleep(0)

    def stop(self) -> None:
        self.running = False

        if not self.socket:
            return

        if not self.socket_is_closed:
            self.close_socket()
            self.setup_event_loop()
            self.loop.run_until_complete(self.stopping())

        self.log.info('[SUBSCRIBER] Stopped.')
        print(f'[{self.log.name}][SUBSCRIBER] Stopped.')