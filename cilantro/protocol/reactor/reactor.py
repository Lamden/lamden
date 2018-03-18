import asyncio
import zmq
import zmq.asyncio
import aioprocessing
from threading import Thread
import logging
from cilantro.logger import get_logger
import time
from collections import defaultdict


class ZMQLoop:
    PUB, SUB, REQ = range(3)
    SOCKET, FUTURE = range(2)

    def __init__(self, parent):
        self.log = get_logger("Reactor.ZMQLoop")
        self.parent = parent

        # self.loop = asyncio.new_event_loop()
        self.loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)

        self.sockets = defaultdict(dict)
        self.ctx = zmq.asyncio.Context()
        self.log.critical("CREATED WITH ZMQ CONTEXT: {}".format(self.ctx))

    async def receive(self, socket, url, callback):
        self.log.warning("--- Starting Subscribing To URL: {} ---".format(url))
        while True:
            self.log.debug("({}) zmqloop waiting for msg...".format(url))
            msg = await socket.recv()
            self.log.debug("({}) zmqloop got msg: {}".format(url, msg))

            assert hasattr(self.parent, callback), "Callback {} not found on parent object {}"\
                .format(callback, self.parent)
            getattr(self.parent, callback)(msg)


class CommandMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        clsobj.log = get_logger(clsobj.__name__)

        if not hasattr(clsobj, 'registry'):
            clsobj.registry = {}
        clsobj.registry[clsobj.__name__] = clsobj

        return clsobj


class Command(metaclass=CommandMeta):
    pass


class AddSubCommand(Command):
    @classmethod
    def execute(cls, zl: ZMQLoop, url, callback):
        assert url not in zl.sockets[ZMQLoop.SUB], \
            "Subscriber already exists for that socket (sockets={})".format(zl.sockets)

        socket = zl.ctx.socket(socket_type=zmq.SUB)
        cls.log.debug("created socket: {}".format(socket))
        socket.setsockopt(zmq.SUBSCRIBE, b'')
        socket.connect(url)
        future = asyncio.ensure_future(zl.receive(socket, url, callback))

        zl.sockets[ZMQLoop.SUB][url] = {}
        zl.sockets[ZMQLoop.SUB][url][ZMQLoop.SOCKET] = socket
        zl.sockets[ZMQLoop.SUB][url][ZMQLoop.FUTURE] = future


class RemoveSubCommand(Command):
    @classmethod
    def execute(cls, zl: ZMQLoop, url):
        assert url in zl.sockets[ZMQLoop.SUB], "Cannot remove publisher socket {} not in sockets={}" \
            .format(url, zl.sockets)

        cls.log.warning("--- Unsubscribing to URL {} ---".format(url))
        zl.sockets[ZMQLoop.SUB][url][ZMQLoop.FUTURE].cancel()
        zl.sockets[ZMQLoop.SUB][url][ZMQLoop.SOCKET].close()
        zl.sockets[ZMQLoop.SUB][url][ZMQLoop.SOCKET] = None


class AddPubCommand(Command):
    @classmethod
    def execute(cls, zl: ZMQLoop, url):
        assert url not in zl.sockets[ZMQLoop.PUB], "Cannot add publisher {} that already exists in sockets {}" \
            .format(url, zl.sockets)

        cls.log.warning("-- Adding publisher {} --".format(url))
        zl.sockets[ZMQLoop.PUB][url] = {}
        socket = zl.ctx.socket(socket_type=zmq.PUB)
        socket.bind(url)
        zl.sockets[ZMQLoop.PUB][url][ZMQLoop.SOCKET] = socket

        # TODO -- fix hack to solve late joiner syndrome. Read CH 2 of ZMQ Guide for real solution
        time.sleep(0.2)


class RemovePubCommand(Command):
    @classmethod
    def execute(cls, zl: ZMQLoop, url):
        assert url in zl.sockets[ZMQLoop.PUB], "Cannot remove publisher socket {} not in sockets={}" \
            .format(url, zl.sockets)
        zl.sockets[ZMQLoop.PUB][url][ZMQLoop.SOCKET].close()
        zl.sockets[ZMQLoop.PUB][url][ZMQLoop.SOCKET] = None
        del zl.sockets[ZMQLoop.PUB][url]


class SendPubCommand(Command):
    @classmethod
    def execute(cls, zl: ZMQLoop, url, data):
        assert url in zl.sockets[ZMQLoop.PUB], "URL {} not found in sockets {}".format(url, zl.sockets)
        zl.log.debug("Publishing data {} to url {}".format(data, url))
        zl.sockets[ZMQLoop.PUB][url][ZMQLoop.SOCKET].send(data)


class ReactorCore(Thread):
    READY_SIG = 'READY'
    PAUSE_SIG = 'PAUSE'

    def __init__(self, queue, parent):
        super().__init__()
        self.log = get_logger("Reactor")

        # Comment out below for more granularity in debugging
        # self.log.setLevel(logging.INFO)

        self.queue = queue
        self.parent = parent
        self.parent_ready = False
        self.cmd_queue = []
        self.zmq_loop = None

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)



    def run(self):
        super().run()
        self.log.debug("ReactorCore Run started")
        asyncio.set_event_loop(self.loop)
        self.zmq_loop = ZMQLoop(parent=self.parent)
        self.loop.run_until_complete(asyncio.gather(self.read_queue(),))

    async def read_queue(self):
        self.log.warning("-- Starting Queue Listening --")
        while True:
            self.log.debug("Reading queue...")
            cmd = await self.queue.coro_get()
            self.log.debug("Got cmd from queue: {}".format(cmd))
            self.process_cmd(cmd)

    def process_cmd(self, cmd):
        # Handle Reactor event Cmds vs. ZMQLoop commands
        if type(cmd) == str:
            if cmd == self.READY_SIG:
                self.log.debug("Setting parent_ready to True...flushing {} cmds".format(len(self.cmd_queue)))
                self.parent_ready = True
                self.cmd_queue.reverse()
                while len(self.cmd_queue) > 0:
                    c = self.cmd_queue.pop()
                    self.execute_cmd(c)
                self.log.debug("Done flushing cmds")
            elif cmd == self.PAUSE_SIG:
                self.parent_ready = False
                self.log.debug("Holding off any new command executions")
            else:
                self.log.error("Unknown string cmd passed: {}".format(cmd))
            return

        assert type(cmd) == tuple, "Only a tuple object can be inserted into the queue"
        assert cmd[0] in Command.registry, "Command: {} not found in registry {}".format(cmd[0], Command.registry)
        assert len(cmd) <= 2, "Tuple must have 1 or 2 objects, (CommandName, kwargs_dict), second is optional"
        if len(cmd) == 2: assert type(cmd[1]) == dict, "Second value of tuple must be a kwargs dict"

        if self.parent_ready:
            self.log.debug("Executing command: {}".format(cmd))
            self.execute_cmd(cmd)
        else:
            self.log.debug("Parent not ready. Storing cmd {}".format(cmd))
            self.cmd_queue.append(cmd)

    def execute_cmd(self, cmd):
        Command.registry[cmd[0]].execute(zl=self.zmq_loop, ** cmd[1])


class NetworkReactor:
    def __init__(self, parent):
        self.log = get_logger("NetworkReactor")

        self.q = aioprocessing.AioQueue()
        self.reactor = ReactorCore(queue=self.q, parent=parent)
        self.reactor.start()

    def notify_ready(self):
        self.q.coro_put(ReactorCore.READY_SIG)

    def add_sub(self, **kwargs):
        self.q.coro_put((AddSubCommand.__name__, kwargs))

    def remove_sub(self, **kwargs):
        self.q.coro_put((RemoveSubCommand.__name__, kwargs))

    def pub(self, **kwargs):
        self.q.coro_put((SendPubCommand.__name__, kwargs))

    def add_pub(self, **kwargs):
        self.q.coro_put((AddPubCommand.__name__, kwargs))

    def remove_pub(self, **kwargs):
        self.q.coro_put((RemovePubCommand.__name__, kwargs))

    def prove_im_nonblocking(self):
        self.log.debug("xD")
