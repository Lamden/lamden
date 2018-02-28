from multiprocessing import Process, Pipe, Queue
from cilantro.serialization import JSONSerializer
import zmq
import asyncio
from cilantro.logger.base import get_logger



class ZMQScaffolding:
    def __init__(self, base_url='127.0.0.1', subscriber_port='1111', publisher_port='9998', filters=(b'', )):

        self.base_url = base_url
        self.subscriber_port = subscriber_port
        self.publisher_port = publisher_port
        self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)
        self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

        self.context = None
        self.sub_socket = None
        self.pub_socket = None

        self.filters = filters

        self.logger = get_logger()
        print("a")

    def connect(self):
        self.context = zmq.Context()

        self.sub_socket = self.context.socket(socket_type=zmq.SUB)
        self.pub_socket = self.context.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.publisher_url)

        self.logger.info("ZMQ Binding to sub_socket")
        self.sub_socket.bind(self.subscriber_url)

        for f in self.filters:
            self.sub_socket.subscribe(f)


class ConveyorBelt:
    def __init__(self, callback):
        self.callback = callback

    async def loop(self, **kwargs):
        raise NotImplementedError


class ZMQConveyorBelt(ConveyorBelt):
    async def loop(self, sub_socket=None):
        while True:
            msg = await sub_socket.recv()
            self.callback(msg)


class LocalConveyorBelt(ConveyorBelt):
    async def loop(self, queue=None):
        while True:
            msg = queue.get()
            self.callback(msg)


class BaseNode:
    def __init__(self, serializer=JSONSerializer, start=True, **kwargs):
        self.queue = Queue()
        self.serializer = serializer
        self.process = Process(target=self.run)

        self.message_queue = ZMQScaffolding(**kwargs)

        self.zmq_conveyor_belt = ZMQConveyorBelt(callback=self.zmq_recv_callback)
        self.mpq_conveyor_belt = ZMQConveyorBelt(callback=self.mpq_recv_callback)

        self.conveyor_belts = [self.zmq_conveyor_belt, self.mpq_conveyor_belt]

        self.logger = get_logger()
        if start:
            self.process.start()


    def run(self):
        self.logger.info('Running async event loop.')
        self.message_queue.connect()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(asyncio.wait([c.loop() for c in self.conveyor_belts]))

    def zmq_recv_callback(self, msg):
        raise NotImplementedError

    def mpq_recv_callback(self, msg):
        raise NotImplementedError

    def terminate(self):
        self.process.terminate()

    def mp_eval(self, eval_statement):
        self.queue.put(('EVAL', eval_statement))
