from multiprocessing import Process, Queue, Pipe
import zmq
import asyncio

from cilantro import Constants
import sys


class ZMQScaffolding:
    def __init__(self,
                 base_url=Constants.BaseNode.BaseUrl,
                 subscriber_port=Constants.BaseNode.SubscriberPort,
                 publisher_port=Constants.BaseNode.PublisherPort,
                 filters=(b'', )):
        self.base_url = base_url
        self.subscriber_port = subscriber_port

        self.publisher_port = publisher_port

        self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)
        self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

        self.context = None
        self.sub_socket = None
        self.pub_socket = None

        self.filters = filters

    def connect(self):
        self.context = zmq.Context()

        self.sub_socket = self.context.socket(socket_type=zmq.SUB)

        self.pub_socket = self.context.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.publisher_url)

        self.sub_socket.bind(self.subscriber_url)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')
        #self.sub_socket.subscribe(b'')
        print('binding')
        # for f in self.filters:
        #     self.sub_socket.subscribe(f)


class ConveyorBelt:
    def __init__(self, callback, queue=None):
        self.callback = callback
        self.queue = queue

    async def loop(self):
        raise NotImplementedError


class ZMQConveyorBelt(ConveyorBelt):
    async def loop(self):
        assert self.queue is not None
        while True:
            print('waiting for that good shit')
            sys.stdout.flush()
            try:
                msg = self.queue.sub_socket.recv()
            except Exception as e:
                print(e)
            self.callback(msg)


class LocalConveyorBelt(ConveyorBelt):
    async def loop(self):
        assert self.queue is not None
        while True:
            print('message recieved')
            msg = self.queue.get()
            print(msg)
            self.callback(msg)

class BaseNode:
    def __init__(self, start=True, **kwargs):
        self.serializer = Constants.Protocol.Serialization

        # set up the multiprocessing setup
        self.mpq_queue = Queue()
        self.main_queue = Queue()

        self.message_queue = ZMQScaffolding(**kwargs)

        self.zmq_conveyor_belt = ZMQConveyorBelt(callback=self.zmq_recv_callback)
        self.mpq_conveyor_belt = LocalConveyorBelt(callback=self.mpq_recv_callback, queue=self.mpq_queue)

        self.conveyor_belts = [self.zmq_conveyor_belt, self.mpq_conveyor_belt]

        self.process = Process(target=self.run)
        if start:
            self.process.start()

    def run(self):
        self.message_queue.connect()
        self.zmq_conveyor_belt.queue = self.message_queue
        loop = asyncio.new_event_loop()
        loop.run_until_complete(asyncio.wait([c.loop() for c in self.conveyor_belts]))

    def zmq_recv_callback(self, msg):
        raise NotImplementedError

    def mpq_recv_callback(self, msg):
        raise NotImplementedError

    def terminate(self):
        self.process.terminate()
