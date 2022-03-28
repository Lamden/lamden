import asyncio
import threading
import zmq
import zmq.auth
from lamden.logger.base import get_logger

class Subscriber(threading.Thread):
    def __init__(self, address: str, topics = [''], callback = None, ctx = zmq.Context(), logger=None):
        threading.Thread.__init__(self)
        self.Lock = threading.Lock()

        self.log = logger or get_logger("SUBSCRIBER")
        # Configure the listening socket

        self.running = False
        self.checking = False

        self.address = address
        self.callback = callback

        self.ctx = ctx
        self.loop = None

        self.socket = None

        self.topics = topics


    @property
    def is_running(self):
        return self.running

    @property
    def socket_is_bound(self):
        try:
            return len(self.socket.LAST_ENDPOINT) > 0
        except AttributeError:
            return False

    @property
    def socket_is_closed(self):
        try:
            return self.socket.closed
        except AttributeError:
            return True

    def setup_event_loop(self):
        try:
            self.loop = asyncio.get_event_loop()
        except Exception:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def create_socket(self):
        self.socket = self.ctx.socket(zmq.SUB)

    def connect_socket(self):
        self.socket.connect(self.address)

    def subscribe_to_topics(self):
        for topic in self.topics:
            self.socket.setsockopt(zmq.SUBSCRIBE, (topic.encode('utf8')))

    def add_topic(self, topic: str):
        if not isinstance(topic, str):
            raise TypeError("Topic must be string.")

        self.topics.append(topic)
        self.socket.setsockopt(zmq.SUBSCRIBE, (topic.encode('utf8')))

    def run(self):
        self.create_socket()
        self.connect_socket()

        self.subscriber_thread()

        self.log.info(f'[SUBSCRIBER] Running..')
        print(f'[{self.log.name}][SUBSCRIBER] Running..')

    def subscriber_thread(self):
        self.running = True

        while self.running:
            event = self.socket.poll(timeout=50, flags=zmq.POLLIN)

            if event:
                data = self.socket.recv_multipart()

                self.log.info(f'[SUBSCRIBER] Got event from {self.address}')
                print(f'[{self.log.name}][SUBSCRIBER] Got event from {self.address}')

                if self.callback:
                    self.callback(data)

        self.socket.close()

    async def stopping(self):
        while not self.socket_is_closed:
            await asyncio.sleep(0)

    def stop(self):
        if self.running:
            self.running = False

            self.setup_event_loop()
            self.loop.run_until_complete(self.stopping())

            self.log.info('[SUBSCRIBER] Stopping.')
            print(f'[{self.log.name}][SUBSCRIBER] Stopping.')