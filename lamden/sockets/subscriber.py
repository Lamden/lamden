import asyncio
import zmq
import zmq.asyncio

from lamden.logger.base import get_logger

from typing import Callable

EXCEPTION_TOPIC_NOT_STRING = "Topic must be string."
EXCEPTION_NO_SOCKET = "No socket created."

class Subscriber():
    def __init__(self, address: str, callback: Callable = None, topics: list=[], ctx: zmq.Context = None):
        self.running = False

        self.address = address
        self.callback = callback
        self.topics = list(topics)

        self.ctx = ctx or zmq.asyncio.Context().instance()
        self.check_for_messages_task = None

        self.loop = None
        self.socket = None

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def is_checking_for_messages(self) -> bool:
        if not self.check_for_messages_task:
            return False
        return not self.check_for_messages_task.done()

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

    def log(self, log_type: str, message: str) -> None:
        if self.address:
            named_message = f'[SUBSCRIBER] {message}'
            logger = get_logger(f'{self.address}')
            print(named_message)
        else:
            named_message = message
            logger = get_logger(f'SUBSCRIBER')
            print(f'[SUBSCRIBER] ß{named_message}')

        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

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

    def connect_socket(self):
        if not self.socket:
            self.create_socket()

        try:
            self.socket.bind(self.address)
        except zmq.error.ZMQError as err:
            self.log('error', err)
            pass


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

        if self.socket_is_bound:
            self.setup_event_loop()
            self.check_for_messages_task = asyncio.ensure_future(self.check_for_messages())

            self.log('info', 'Started.')

    async def messages_waiting(self, timeout: int = 1) -> bool:
        return await self.socket.poll(timeout=timeout) > 0

    async def check_for_messages(self) -> None:
        self.running = True

        # initial poll to contact publisher
        await self.messages_waiting()

        while self.running:
            if await self.messages_waiting(timeout=50):
                data = await self.socket.recv_multipart()

                self.log('info', f'Got event from {self.address}')

                if self.callback:
                    self.callback(data)

    async def stop_checking_for_messages(self):
        self.running = False

        while self.is_checking_for_messages:
            await asyncio.sleep(0)

    def close_socket(self) -> None:
        if self.socket_is_closed:
            return

        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.close()

    async def stopping(self) -> None:
        while not self.socket_is_closed:
            await asyncio.sleep(0)

    async def stop(self) -> None:
        self.running = False

        if self.loop:
            await self.stop_checking_for_messages()

        if not self.socket_is_closed:
            self.close_socket()

            await self.stopping()

        self.log('info', 'Stopped.')