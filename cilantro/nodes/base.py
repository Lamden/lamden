from multiprocessing import Process, Pipe, Queue
from cilantro.serialization import JSONSerializer
import zmq
import asyncio


class ZMQScaffolding:
    def __init__(self, base_url='127.0.0.1', subscriber_port='1111', publisher_port='9998', filters=(b'', )):
        self.base_url = base_url
        self.subscriber_port = subscriber_port
        self.publisher_port = publisher_port
        self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)
        self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

        self.filters = filters

    def connect(self):
        self.context = zmq.Context()

        self.sub_socket = self.context.socket(socket_type=zmq.SUB)
        self.pub_socket = self.context.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.publisher_url)

        print("binding to url: ", self.subscriber_url)
        self.sub_socket.bind(self.subscriber_url)

        for filter in self.filters:
            self.sub_socket.subscribe(filter)


class BaseNode:
    def __init__(self, serializer=JSONSerializer, start=True, **kwargs):
        self.queue = Queue()
        self.serializer = serializer
        self.process = Process(target=self.run)

        self.message_queue = ZMQScaffolding(**kwargs)

        if start:
            self.process.start()

    # start multiprocess / non-blocking event loop for the queues
    def run(self):
        print('running')
        self.message_queue.connect()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(asyncio.wait([
            self.zmq_loop(),
            self.mp_loop(),
        ]))

    async def zmq_loop(self):
        while True:
            print('zmq')
            msg = await self.message_queue.sub_socket.recv()
            self.handle_zmq_msg(msg)

    async def mp_loop(self):
        while True:
            print('ass!')
            msg = self.queue.get()
            print('message recieved')
            self.handle_mp_msg(msg)

    # move towards this abstraction eventually
    async def listen(self, getter, callback):
        while True:
            msg = getter()
            callback(msg)

    # callback methods for local queue and zmq
    def handle_zmq_msg(self, msg):
        raise NotImplementedError

    def handle_mp_msg(self, msg):
        print('yes')
        if msg[0] == 'EVAL':
            eval(msg[1])

    def terminate(self):
        self.process.terminate()

    def mp_eval(self, eval_statement):
        self.queue.put(('EVAL', eval_statement))
