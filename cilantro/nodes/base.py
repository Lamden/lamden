from multiprocessing import Process
import zmq
from cilantro import Constants
import asyncio
from aioprocessing import AioPipe


class Node(Process):
    def __init__(self, base_url=Constants.BaseNode.BaseUrl, sub_port=9999, pub_port=9998):
        super().__init__()
        self.parent_pipe, self.child_pipe = AioPipe()

        # establish base url
        self.base_url = base_url

        # setup subscriber constants
        self.subscriber_port = sub_port
        self.subscriber_url = 'tcp://{}:{}'.format(self.base_url, self.subscriber_port)

        # setup publisher constants
        self.publisher_port = pub_port
        self.publisher_url = 'tcp://{}:{}'.format(self.base_url, self.publisher_port)

        # set context and sockets to none until process starts because multiprocessing zmq is funky
        self.context = None
        self.sub_socket = None
        self.pub_socket = None

    def run(self, *args):
        super().run()

        self.context = zmq.Context()

        self.sub_socket = self.context.socket(socket_type=zmq.SUB)

        self.sub_socket.bind(self.subscriber_url)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')

        self.pub_socket = self.context.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.publisher_url)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(self.listen())

    async def listen(self):
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self.receive, self.child_pipe, self.pipe_callback),
            loop.run_in_executor(None, self.receive, self.sub_socket, self.zmq_callback)
        ]
        await asyncio.wait(tasks)

    @staticmethod
    def receive(socket, callback):
        while True:
            callback(socket.recv())

    def zmq_callback(self, msg):
        raise NotImplementedError

    def pipe_callback(self, msg):
        raise NotImplementedError
