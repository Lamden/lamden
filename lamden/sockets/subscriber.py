import asyncio
import zmq
import zmq.asyncio

from lamden.logger.base import get_logger

from typing import Callable

class Subscriber():
    def __init__(self, address: str, callback: Callable = None, logger=None, topics: list=['']):
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
        except AttributeError:
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
        except Exception:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def create_socket(self) -> None:
        self.socket = self.ctx.socket(zmq.SUB)

    def connect_socket(self) -> None:
        if not self.socket:
            self.create_socket()
        self.socket.connect(self.address)

    def subscribe_to_topics(self) -> None:
        for topic in self.topics:
            self.socket.setsockopt(zmq.SUBSCRIBE, topic.encode('utf8'))

    def add_topic(self, topic: str) -> None:
        if not isinstance(topic, str):
            raise TypeError("Topic must be string.")

        self.topics.append(topic)
        self.socket.setsockopt(zmq.SUBSCRIBE, topic.encode('utf8'))

    def start(self) -> None:
        self.create_socket()
        self.connect_socket()
        self.setup_event_loop()

        asyncio.ensure_future(self.check_for_messages())

        self.log.info('[SUBSCRIBER] Running...')
        print(f'[{self.log.name}][SUBSCRIBER] Running...')

    async def check_for_messages(self) -> None:
        self.running = True

        while self.running:
            event = await self.socket.poll(timeout=50, flags=zmq.POLLIN)

            if event:
                data = await self.socket.recv_multipart()

                self.log.info(f'[SUBSCRIBER] Got event from {self.address}')
                print(f'[{self.log.name}][SUBSCRIBER] Got event from {self.address}')

                if self.callback:
                    self.callback(data)

        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.close()

    async def stopping(self) -> None:
        while not self.socket_is_closed:
            await asyncio.sleep(0)

    def stop(self) -> None:
        if self.running:
            self.running = False

            self.setup_event_loop()
            self.loop.run_until_complete(self.stopping())

            self.log.info('[SUBSCRIBER] Stopped.')
            print(f'[{self.log.name}][SUBSCRIBER] Stopped.')