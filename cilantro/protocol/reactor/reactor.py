import asyncio
import zmq
import zmq.asyncio
import aioprocessing
from threading import Thread
from cilantro.logger import get_logger
import time


URL = "tcp://127.0.0.1:5566"
URL2 = "tcp://127.0.0.1:5577"
URL3 = "tcp://127.0.0.1:5588"
URL4 = "tcp://127.0.0.1:5599"


class Command:

    SUB, UNSUB, PUB, UNPUB, UNSUB_ALL = range(5)

    def __init__(self, cmd, **kwargs):
        self.type = cmd
        self.kwargs = kwargs
        # TODO -- validate cmd and kwargs with assertions (should not have any hardcore validation irl, i dont think?
        # b/c there would be overhead, and it might now be an attack vecotr idk

    def __repr__(self):
        return "cmd={}, {}".format(self.type, self.kwargs)


class ReactorCore(Thread):

    def __init__(self, queue):
        super().__init__()
        self.log = get_logger("Reactor")
        self.queue = queue

        # Is this really the right way to do Thread subclassing? Having to instantiate all ur stuff in the run() method
        # feels lowkey ratchet
        self.loop = asyncio.new_event_loop()
        self.sockets, self.ctx = None, None
        asyncio.set_event_loop(self.loop)

    def run(self):
        super().run()
        self.log.debug("ReactorCore Run started")

        self.sockets = {'PUB': {}, 'SUB': {}}
        self.ctx = zmq.asyncio.Context()
        asyncio.set_event_loop(self.loop)

        self.loop.run_until_complete(asyncio.gather(self.read_queue(),))

    async def read_queue(self):
        self.log.warning("-- Starting Queue Listening --")
        while True:
            self.log.debug("Reading queue...")

            cmd = await self.queue.coro_get()
            assert type(cmd) == Command, "Only a Command object can be inserted into the queue"
            self.log.info("Got data from queue: {}".format(cmd))
            self.execute(cmd)

    def execute(self, cmd: Command):
        self.log.info("Executing command: {}".format(cmd))

        if cmd.type == Command.SUB:
            url = cmd.kwargs['url']
            assert url not in self.sockets['SUB'], \
                "Subscriber already exists for that socket (sockets={})".format(self.sockets)

            socket = self.ctx.socket(socket_type=zmq.SUB)
            self.log.debug("created socket: {}".format(socket))
            socket.setsockopt(zmq.SUBSCRIBE, b'')
            socket.connect(cmd.kwargs['url'])
            future = asyncio.ensure_future(self.receive(socket, cmd.kwargs['callback']))

            self.sockets['SUB'][url] = {}
            self.sockets['SUB'][url]['SOCKET'] = socket
            self.sockets['SUB'][url]['FUTURE'] = future

        elif cmd.type == Command.PUB:
            url = cmd.kwargs['url']
            if url not in self.sockets['PUB']:
                self.sockets['PUB'][url] = {}
                socket = self.ctx.socket(socket_type=zmq.PUB)
                socket.bind(cmd.kwargs['url'])
                self.sockets['PUB'][url]['SOCKET'] = socket

                # TODO -- fix hack to solve late joiner syndrome. Read CH 2 of ZMQ Guide for real solution
                time.sleep(0.2)

            self.log.debug("Publishing data {} to url {}".format(cmd.kwargs['data'], cmd.kwargs['url']))
            self.sockets['PUB'][url]['SOCKET'].send(cmd.kwargs['data'])

        elif cmd.type == Command.UNPUB:
            url = cmd.kwargs['url']
            assert url in self.sockets['PUB'], "Cannot remove publisher socket {} not in sockets={}"\
                .format(url, self.sockets)

            self.sockets['PUB'][url]['SOCKET'].close()
            self.sockets['PUB'][url]['SOCKET'] = None
            del self.sockets['PUB'][url]

        elif cmd.type == Command.UNSUB:
            url = cmd.kwargs['url']
            assert url in self.sockets['SUB'], "Cannot unsubscribe to url {} because it doesnt exist in our sockets={}"\
                .format(url, self.sockets)

            self.log.debug("Unsubscribing to URL {}...".format(url))
            self.sockets['SUB'][url]['FUTURE'].cancel()
            self.log.debug("Closing socket...")
            self.sockets['SUB'][url]['SOCKET'].close()
            del self.sockets['SUB'][url]

        else:
            self.log.error("Unknown command type: {}".format(cmd))
            raise NotImplementedError("Unknown command type: {}".format(cmd))

    async def receive(self, socket, callback):
        # could just use self.socket here
        self.log.warning("--- Starting Receiving for socket: {} ----".format(socket))
        while True:
            self.log.info("waiting for msg...")
            msg = await socket.recv()
            callback(msg)
            self.log.info("got msg: {}".format(msg))


class NetworkReactor:
    def __init__(self):
        self.log = get_logger("NetworkReactor")

        self.q = aioprocessing.AioQueue()
        self.reactor = ReactorCore(queue=self.q)
        self.reactor.start()

    def execute(self, cmd, **kwargs):
        self.q.coro_put(Command(cmd, **kwargs))

    def add_sub(self, **kwargs):
        self.q.coro_put(Command(Command.SUB, **kwargs))

    def remove_sub(self, **kwargs):
        self.q.coro_put(Command(Command.UNSUB, **kwargs))

    def pub(self, **kwargs):
        self.q.coro_put(Command(Command.PUB, **kwargs))

    def remove_pub(self, **kwargs):
        self.q.coro_put(Command(Command.PUB, **kwargs))

    def prove_im_nonblocking(self):
        self.log.debug("xD")
