from multiprocessing import Process
import zmq
from cilantro import Constants
import asyncio
from aioprocessing import AioPipe
from cilantro.logger import get_logger

import sys
if sys.platform != 'win32':
    import uvloop
    # asyncio.set_event_loop_policy(uvloop.EventLoopPolicy)


class Node(Process):
    def __init__(self, base_url=Constants.BaseNode.BaseUrl, sub_port=7777, pub_port=9998):
        super().__init__()
        print(sub_port)
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
        # print("Recieved something at socket {} wtih callback {}".format(socket, callback))
        while True:
            callback(socket.recv())

    def zmq_callback(self, msg):
        raise NotImplementedError

    def pipe_callback(self, msg):
        raise NotImplementedError

BIND = 'BIND'
CONNECT = 'CONNECT'


class Subprocess(Process):
    """
    Subprocess is an abstract class for putting long running asynchronous networking loops on multiple processors.
    This allows a node to have multiple processes for sending and receiving messages without any blocking functionality.
    Input to each process is managed through a multiprocessing pipe. Output is piped back with a different pipe.

    For example, if a delegate wants to have publisher / subscriber functionality for listening to witnesses but also
    wants a request / response pattern between other delegates, this can be achieved by spinning up several subprocesses
    to listen to messages and send them to the appropriate parties.

    Subprocesses can be terminated in a non-blocking manner and instantiated at will. Subprocesses have two callbacks,
    one for when input on the pipe is received and one when a message is received.
    """
    def __init__(self, name, connection_type, socket_type, url):
        super().__init__()
        self.pipe, self._pipe = AioPipe()

        self.name = name

        assert connection_type == BIND or connection_type == CONNECT, \
            'Invalid connection type provided.'

        self.connection_type = connection_type
        self.socket_type = socket_type
        self.url = url

        self.context = None
        self.socket = None

    def run(self, *args):
        super().run()

        self.context = zmq.Context()
        self.socket = self.context.socket(socket_type=self.socket_type)

        self.socket.connect(self.url) if self.connection_type == CONNECT \
            else self.socket.bind(self.url)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(self.listen())

    async def listen(self):
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self.receive, self._pipe, self.pipe_callback),
            loop.run_in_executor(None, self.receive, self.socket, self.zmq_callback)
        ]
        await asyncio.wait(tasks)

    @staticmethod
    def receive(socket, callback):
        while True:
            print("socket {} waiting for recv with callback {}...".format(socket, callback))
            callback(socket.recv())
            print("process got recv")

    def zmq_callback(self, msg):
        raise NotImplementedError

    def pipe_callback(self, msg):
        raise NotImplementedError


'''
    Subprocess can probably be slimmed down to a more functional model
'''


def pipe_listener():
    def listen():
        pl_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(pl_loop)

        pl_loop.run_until_complete(loop())

    async def loop():
        sub_loop = asyncio.get_event_loop()
        await asyncio.wait([sub_loop.run_in_executor(None, receive)])

    def receive():
        while True:
            pipe.send(_pipe.recv())

    pipe, _pipe = AioPipe()
    process = Process(target=listen)

    return pipe, process


def zmq_listener(socket_type, connection_type, url):
    def listen(*args):
        log = args[-1]
        context = zmq.Context()

        socket = context.socket(socket_type=args[0])

        socket.bind(args[2]) if args[1] == BIND else \
            socket.connect(args[2])

        if args[0] == zmq.SUB:
            socket.setsockopt(zmq.SUBSCRIBE, b'')

        log.debug("{} on {}".format(args[1], args[2]))

        zmq_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(zmq_loop)

        zmq_loop.run_until_complete(loop(socket))

    async def loop(socket):
        sub_loop = asyncio.get_event_loop()
        await asyncio.wait([sub_loop.run_in_executor(None, receive, socket)])

    def receive(socket):
        log = get_logger('ZMQ_LISTENER')
        log.debug("Setting up RECV on ZMQ_LISTENER")
        while True:
            log.debug("Waiting for a message on delegate")
            _pipe.send(socket.recv())
            log.debug("Got a message on delegate")

    log = get_logger('ZMQ_LISTENER')
    pipe, _pipe = AioPipe()
    process = Process(target=listen, args=(socket_type, connection_type, url, log,))

    return pipe, process


def zmq_sender(socket_type, connection_type, url):
    def listen(*args):
        context = zmq.Context()

        socket = context.socket(socket_type=args[0])

        socket.bind(args[2]) if args[1] == BIND else \
            socket.connect(args[2])

        zmq_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(zmq_loop)

        zmq_loop.run_until_complete(loop(socket))

    async def loop(socket):
        sub_loop = asyncio.get_event_loop()
        await asyncio.wait([sub_loop.run_in_executor(None, receive, socket)])

    def receive(socket):
        while True:
            socket.send(_pipe.recv())

    pipe, _pipe = AioPipe()
    process = Process(target=listen, args=(socket_type, connection_type, url, ))

    return pipe, process