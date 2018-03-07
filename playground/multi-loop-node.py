from multiprocessing import Process
import zmq
import asyncio
from aioprocessing import AioPipe

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
        self.input, self.child_input = AioPipe()
        self.output, self.child_output = AioPipe()

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

        loop.run_until_complete(self.listen)

    async def listen(self):
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self.receive, self.child_input, self.pipe_callback),
            loop.run_in_executor(None, self.receive, self.socket, self.zmq_callback)
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