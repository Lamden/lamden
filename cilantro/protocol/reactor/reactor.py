import asyncio
import zmq
import zmq.asyncio
import aioprocessing
from multiprocessing import Process, Queue
from threading import Thread
import logging
from cilantro.logger import get_logger
from random import random
import time


class Command:
    ADD_SUB, REMOVE_SUB, ADD_PUB, REMOVE_PUB, PUB, READY = range(6)

    def __init__(self, cmd, **kwargs):
        self.type = cmd
        self.kwargs = kwargs
        # TODO -- validate cmd and kwargs with assertions (should not have any hardcore validation irl), i dont think?

    def __repr__(self):
        return "cmd={}, {}".format(self.type, self.kwargs)

class ReactorCore(Thread):

    def __init__(self, queue, parent):
        super().__init__()
        self.log = get_logger("Reactor")

        # Comment out below for more granularity in debugging
        self.log.setLevel(logging.INFO)

        self.queue = queue
        self.parent = parent
        self.parent_ready = False
        self.cmd_queue = []

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
        self.log.critical("CREATED WITH ZMQ CONTEXT: {}".format(self.ctx))
        asyncio.set_event_loop(self.loop)

        self.loop.run_until_complete(asyncio.gather(self.read_queue(),))

    async def read_queue(self):
        self.log.warning("-- Starting Queue Listening --")
        while True:
            self.log.debug("Reading queue...")
            cmd = await self.queue.coro_get()
            assert type(cmd) == Command, "Only a Command object can be inserted into the queue"
            self.log.debug("Got data from queue: {}".format(cmd))
            self.execute(cmd)

    def execute(self, cmd: Command):
        self.log.debug("exec cmd: {}".format(cmd))
        if cmd.type == Command.READY:
            self.log.debug("Setting parent_ready to True...flushing {} cmds".format(len(self.cmd_queue)))
            self.parent_ready = True
            self.cmd_queue.reverse()
            while len(self.cmd_queue) > 0:
                c = self.cmd_queue.pop()
                self.log.debug("Executing cmd: {}".format(c))
                self.execute(c)
            self.log.debug("Done flushing cmds")
            return

        if self.parent_ready:
            self.log.debug("Executing command: {}".format(cmd))
        else:
            self.log.debug("Parent not ready. Storing cmd {}".format(cmd))
            self.cmd_queue.append(cmd)
            return

        if cmd.type == Command.ADD_SUB:
            url = cmd.kwargs['url']
            assert url not in self.sockets['SUB'], \
                "Subscriber already exists for that socket (sockets={})".format(self.sockets)

            socket = self.ctx.socket(socket_type=zmq.SUB)
            self.log.debug("created socket: {}".format(socket))
            socket.setsockopt(zmq.SUBSCRIBE, b'')
            socket.connect(cmd.kwargs['url'])
            future = asyncio.ensure_future(self.receive(socket, cmd.kwargs['callback'], url))

            self.sockets['SUB'][url] = {}
            self.sockets['SUB'][url]['SOCKET'] = socket
            self.sockets['SUB'][url]['FUTURE'] = future

        elif cmd.type == Command.ADD_PUB:
            url = cmd.kwargs['url']
            assert url not in self.sockets['PUB'], "Cannot add publisher {} that already exists in sockets {}"\
                .format(url, self.sockets)

            self.log.warning("-- Adding publisher {} --".format(url))
            self.sockets['PUB'][url] = {}
            socket = self.ctx.socket(socket_type=zmq.PUB)
            socket.bind(cmd.kwargs['url'])
            self.sockets['PUB'][url]['SOCKET'] = socket

        elif cmd.type == Command.PUB:
            url = cmd.kwargs['url']
            if url not in self.sockets['PUB']:
                self.log.warning("-- Adding publisher {} --".format(url))
                self.sockets['PUB'][url] = {}
                socket = self.ctx.socket(socket_type=zmq.PUB)
                socket.bind(cmd.kwargs['url'])
                self.sockets['PUB'][url]['SOCKET'] = socket

                # TODO -- fix hack to solve late joiner syndrome. Read CH 2 of ZMQ Guide for real solution
                time.sleep(0.2)

            self.log.debug("Publishing data {} to url {}".format(cmd.kwargs['data'], cmd.kwargs['url']))
            self.sockets['PUB'][url]['SOCKET'].send(cmd.kwargs['data'])

        elif cmd.type == Command.REMOVE_PUB:
            url = cmd.kwargs['url']
            assert url in self.sockets['PUB'], "Cannot remove publisher socket {} not in sockets={}"\
                .format(url, self.sockets)

            self.sockets['PUB'][url]['SOCKET'].close()
            self.sockets['PUB'][url]['SOCKET'] = None
            del self.sockets['PUB'][url]

        elif cmd.type == Command.REMOVE_SUB:
            url = cmd.kwargs['url']
            assert url in self.sockets['SUB'], "Cannot unsubscribe to url {} because it doesnt exist in our sockets={}"\
                .format(url, self.sockets)

            self.log.warning("--- Unsubscribing to URL {} ---".format(url))
            self.sockets['SUB'][url]['FUTURE'].cancel()
            self.log.debug("Closing socket...")
            self.sockets['SUB'][url]['SOCKET'].close()
            del self.sockets['SUB'][url]

        else:
            self.log.error("Unknown command type: {}".format(cmd))
            raise NotImplementedError("Unknown command type: {}".format(cmd))

    async def receive(self, socket, callback, url):
        self.log.warning("--- Starting Subscribing To URL: {} ---".format(url))
        while True:
            self.log.debug("({}) reactor waiting for msg...".format(url))
            msg = await socket.recv()
            self.log.debug("({}) reactor got msg: {}".format(url, msg))
            assert hasattr(self.parent, callback), "Callback {} not found on parent object {}"\
                .format(callback, self.parent)
            getattr(self.parent, callback)(msg)


class NetworkReactor:
    def __init__(self, parent):
        self.log = get_logger("NetworkReactor")

        self.q = aioprocessing.AioQueue()
        self.reactor = ReactorCore(queue=self.q, parent=parent)
        self.reactor.start()

    def execute(self, cmd, **kwargs):
        self.q.coro_put(Command(cmd, **kwargs))

    def notify_ready(self):
        self.q.coro_put(Command(Command.READY))

    def add_sub(self, **kwargs):
        self.q.coro_put(Command(Command.ADD_SUB, **kwargs))

    def remove_sub(self, **kwargs):
        self.q.coro_put(Command(Command.REMOVE_SUB, **kwargs))

    def pub(self, **kwargs):
        self.q.coro_put(Command(Command.PUB, **kwargs))

    def add_pub(self, **kwargs):
        self.q.coro_put(Command(Command.ADD_PUB, **kwargs))

    def remove_pub(self, **kwargs):
        self.q.coro_put(Command(Command.PUB, **kwargs))

    def prove_im_nonblocking(self):
        self.log.debug("xD")
