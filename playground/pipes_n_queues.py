from multiprocessing import Process, Pipe, Queue

import zmq
from zmq.asyncio import Context
import asyncio

class ZMQScaffolding:
    def __init__(self, base_url='127.0.0.1', subscriber_port='9999', publisher_port='9998', filters=(b'', )):
        self.base_url = base_url
        self.subscriber_port = subscriber_port
        self.publisher_port = publisher_port
        self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)
        self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

        self.filters = filters

    def connect(self):
        self.context = Context()

        self.sub_socket = self.context.socket(socket_type=zmq.SUB)
        self.pub_socket = self.context.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.publisher_url)

        self.sub_socket.bind(self.subscriber_url)

        for filter in self.filters:
            self.sub_socket.subscribe(filter)


CONSUME = 'CONSUME'
BROADCAST = 'BROADCAST'


class Node:
    def __init__(self, serializer, start=True, **kwargs):
        self.queue = Queue()
        self.serializer = serializer
        self.process = Process(target=self.run)

        self.message_queue = ZMQScaffolding(**kwargs)

        if start:
            self.process.start()

    def run(self):
        self.message_queue.connect()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(asyncio.wait([
            self.handle_subscribe_message(),
            self.handle_process_message(),
        ]))

    async def handle_subscribe_message(self):
        while True:
            print('holla')
            msg = await self.message_queue.sub_socket.recv()
            print(msg)

    async def handle_process_message(self):
        while True:
            print('hella')
            msg = self.queue.get()
            print(msg)

    def handle_request(self, request):
        # serialize
        # put on queue
        self.queue.put(request)

    def terminate(self):
        self.process.terminate()

class DumbNode(Node):
    def process_local_queue(self, msg):
        try:
            self.message_queue.pub_socket.send(msg)
        except Exception as e:
            print("error publishing request: {}".format(e))
            return {'status': 'Could not publish request'}

        print("Successfully published request: {}".format(msg))
        return {'status': 'Successfully published request: {}'.format(msg)}


n = DumbNode(serializer=None, start=True)
#n.handle_request(b'something')
import time
time.sleep(1)
n.terminate()