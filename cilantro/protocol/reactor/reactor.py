"""The reactor is the integral component for cilantro nodes that acts as the API for all zmq message passed between
the different node types. All ZMQ message commands such as pub, sub, send, receive, etc, go through the reactor core"""

# TODO - add more description since this module is quite complex and critical


import asyncio
import zmq
import zmq.asyncio
import aioprocessing
from threading import Thread
from cilantro.logger import get_logger
import time
import logging
from collections import defaultdict
from cilantro.messages import Envelope


"""
TODO -- should we be using loop.call_soon_threadsafe(fut.cancel) instead of directly calling cancel()??
see https://docs.python.org/3/library/asyncio-dev.html

TODO -- set socket lingering so pending/queued messages are dealloc's when we close a socket or stop zmq context
using set_socketops and ZMQ_LINGER

USE ZMQ Sockets for communication to the main thread. Have a separate event loop for each thread, main thread
async recv for incoming messages on reactor thread. Reactor thread async recv for command from main thread.
DUDE ALSO I THINK THE PYTHON THREAD JUST PICKLES SHIT LMAO SLOW...ZMQ + CAPNP MIGHT BE FASTER? WHAT ABOUT TIME 
TO BUILD THESE OBJECTS...? RUN SOME TESTS AND BENCHMARKS PLS

This pattern allows us to expand node workers horizontally by having multiple processes or threads that recv
by spinning up multiple "consumer" threads processing @receive events, wih one producer thread (the reactor).

Load balance through an ipc dealer/router proxy to the consumer threads. SCALABILITY SON LETS GO
"""

TIMEOUT_CALLBACK = 'route_timeout'

class ZMQLoop:
    PUB, SUB, DEAL, ROUTE = range(4)
    SOCKET, FUTURE, ID = range(3)

    def __init__(self, parent, loop):
        self.log = get_logger("{}.Reactor".format(parent.log.name))
        self.parent = parent

        self.loop = loop
        asyncio.set_event_loop(loop)

        self.sockets = defaultdict(dict)
        self.ctx = zmq.asyncio.Context()

        self.pending_reqs = {}  # key is msg uuid, value is an asyncio.Handle instance
        self.msg_log = set()  # Set of received msg uuids, (for checking duplicate messages)

    async def receive(self, socket, url, callback):
        self.log.warning("--- Started Receiving on URL: {} with callback {} ---".format(url, callback))
        while True:
            self.log.debug("({}) zmqloop recv waiting for msg...".format(url))
            msg_binary = await socket.recv()
            self.log.debug("({}) zmqloop recv got msg: {}".format(url, msg_binary))

            assert hasattr(self.parent, callback), "Callback {} not found on parent object {}"\
                .format(callback, self.parent)
            # TODO -- cleanup error handling with context managers?
            try:
                msg = self.open_msg(msg_binary)[0]
            except Exception as e:
                self.log.error("Error opening msg: {}, with msg binary: {}".format(e, msg_binary))
                return
            self.call_on_mt(callback, msg)

    async def receive_multipart(self, socket, url, callback):
        self.log.warning("--- Starting Receiving Multipart To URL: {} with callback {} ---".format(url, callback))
        while True:
            self.log.debug("({}) zmqloop recv_multipart waiting for msg...".format(url))
            id, msg_binary = await socket.recv_multipart()
            self.log.debug("({}) zmqloop recv_multipart got msg: {} with id: {}".format(url, msg_binary, id))

            assert hasattr(self.parent, callback), "Callback {} not found on parent object {}"\
                .format(callback, self.parent)
            # TODO -- cleanup error handling with context managers?
            try:
                msg, uuid = self.open_msg(msg_binary)
            except Exception as e:
                self.log.error("Error opening msg: {}, with msg binary: {}".format(e, msg_binary))
                return
            self.call_on_mt(callback, msg, url, id, uuid)

    def check_timeout(self, envelope, url):
        uuid = envelope.uuid
        self.log.critical("Message with from url {} and msg uuid {} timed out (msg={})".format(url, uuid, envelope))
        """
        TODO -- we need to be opening messages as soon as we receive them and queueing them up to run on mainthread
        instead of blocking while mainthread does stuff (as we are currently). Otherwise, we may receive a message
        but the timeout was trigger b/c main thread did not have time to process it.
        Thus, assertion below is really for debugging  
        """
        assert uuid in self.pending_reqs, "UUID {} not found in pending requests {}".format(uuid, self.pending_reqs)

        del self.pending_reqs[uuid]
        self.call_on_mt(TIMEOUT_CALLBACK, envelope.open(), url)

    def open_msg(self, msg_binary):
        # Open msg
        # TODO -- Check for duplicates
        # Remove callback for timeout (if any)
        # TODO -- add error handling for envelope open

        envelope = Envelope.from_bytes(msg_binary)
        msg = envelope.open()

        if envelope.uuid in self.pending_reqs:
            self.log.info("Canceling timeout callback for message with uuid {}".format(envelope.uuid))
            self.pending_reqs[envelope.uuid].cancel()
            del self.pending_reqs[envelope.uuid]

        return msg, envelope.uuid

    def call_on_mt(self, callback, *args):
        assert hasattr(self.parent, callback), "Callback {} not found on parent object {}" \
            .format(TIMEOUT_CALLBACK, self.parent)
        getattr(self.parent, callback)(*args)


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
        cls.log.debug("created socket {} at url {}".format(socket, url))
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
        assert type(data) is Envelope, "Must pass envelope type to send commands"
        zl.log.debug("Publishing data {} to url {}".format(data, url))

        zl.sockets[ZMQLoop.PUB][url][ZMQLoop.SOCKET].send(data.serialize())


class AddDealerCommand(Command):
    @classmethod
    def execute(cls, zl: ZMQLoop, url, callback, id):
        # TODO -- assert we havnt added this dealer already
        socket = zl.ctx.socket(socket_type=zmq.DEALER)
        socket.identity = id.encode('ascii')
        socket.connect(url)
        cls.log.debug("Dealer socket {} created with url {} and identity {}".format(socket, url, id))
        future = asyncio.ensure_future(zl.receive(socket, url, callback))

        zl.sockets[ZMQLoop.DEAL][url] = {}
        zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.SOCKET] = socket
        zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.FUTURE] = future
        zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.ID] = id


class AddRouterCommand(Command):
    @classmethod
    def execute(cls, zl: ZMQLoop, url, callback):
        socket = zl.ctx.socket(socket_type=zmq.ROUTER)
        socket.bind(url)
        cls.log.debug("Router socket {} created at url {}".format(socket, url))
        future = asyncio.ensure_future(zl.receive_multipart(socket, url, callback))

        zl.sockets[ZMQLoop.ROUTE][url] = {}
        zl.sockets[ZMQLoop.ROUTE][url][ZMQLoop.SOCKET] = socket
        zl.sockets[ZMQLoop.ROUTE][url][ZMQLoop.FUTURE] = future


class RequestCommand(Command):
    @classmethod
    def execute(cls, zl: ZMQLoop, url, data, timeout):
        cls.log.debug("Sending request with data {} to url {} with timeout {}".format(data, url, timeout))
        assert type(data) is Envelope, "Must pass envelope type to send commands"
        assert data.uuid not in zl.pending_reqs, "UUID {} for envelope {} already in pending requests {}"\
                                                 .format(data.uuid, data, zl.pending_reqs)
        assert url in zl.sockets[ZMQLoop.DEAL], 'Tried to make a request to url {} that was not in dealer sockets {}'\
                                                .format(url, zl.sockets[ZMQLoop.DEAL])

        if timeout > 0:
            cls.log.info("Adding timeout of {} seconds for request with uuid {} and data {}"
                             .format(timeout, data.uuid, data))
            handle = zl.loop.call_later(timeout, zl.check_timeout, data, url)
            zl.pending_reqs[data.uuid] = handle

        # zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.SOCKET].send(data)
        zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.SOCKET].send_multipart([data.serialize()])


class ReplyCommand(Command):
    @classmethod
    def execute(cls, zl: ZMQLoop, url, data, id):
        assert type(data) is Envelope, "Must pass envelope type to send commands"
        assert url in zl.sockets[ZMQLoop.ROUTE], 'Cannot reply to url {} that is not in router sockets {}'\
            .format(url, zl.sockets[ZMQLoop.ROUTE])
        cls.log.debug("Replying to url {} with id {} and data {}".format(url, id, data))
        zl.sockets[ZMQLoop.ROUTE][url][ZMQLoop.SOCKET].send_multipart([id, data.serialize()])


class ReactorCore(Thread):
    READY_SIG = 'READY'
    PAUSE_SIG = 'PAUSE'

    def __init__(self, queue, parent):
        super().__init__()
        self.log = get_logger("{}.Reactor".format(type(parent).__name__))

        # Comment out below for more granularity in debugging
        self.log.setLevel(logging.INFO)

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
        self.zmq_loop = ZMQLoop(parent=self.parent, loop=self.loop)
        self.loop.run_until_complete(asyncio.gather(self.read_queue(),))

    async def read_queue(self):
        self.log.warning("-- Starting Queue Listening --")
        while True:
            # self.log.debug("Reading queue...")
            cmd = await self.queue.coro_get()
            # self.log.debug("Got cmd from queue: {}".format(cmd))
            self.process_cmd(cmd)

    def process_cmd(self, cmd):
        # Handle Reactor event Cmds vs. ZMQLoop commands
        # TODO -- move this logic into its own command class somehow... it would need an instance of the reactor core
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
        Command.registry[cmd[0]].execute(zl=self.zmq_loop, **cmd[1])


class NetworkReactor:
    def __init__(self, parent):
        self.log = get_logger("NetworkReactor")

        self.q = aioprocessing.AioQueue()
        self.reactor = ReactorCore(queue=self.q, parent=parent)
        self.reactor.start()

    def notify_ready(self):
        self.q.coro_put(ReactorCore.READY_SIG)

    def add_sub(self, callback='route', **kwargs):
        """
        Starts subscribing to 'url'.
        Requires kwargs 'url' of subscriber (as a string)...callback is optional, and by default will forward incoming messages to the
        meta router built into base node

        TODO -- experiment with binding multiple URLS on one socket. This will achieve same functionality, but may be
        more efficient
        """
        kwargs['callback'] = callback
        self.q.coro_put((AddSubCommand.__name__, kwargs))

    def remove_sub(self, **kwargs):
        """
        Requires kwargs 'url' of sub
        """
        self.q.coro_put((RemoveSubCommand.__name__, kwargs))

    def pub(self, **kwargs):
        """
        Publish data 'data on socket connected to 'url'
        Requires kwargs 'url' to publish on, as well as 'data' which is the binary data (type should be bytes) to publish
        If reactor is not already set up to publish on 'url', this will be setup and the data will be published
        """
        self.q.coro_put((SendPubCommand.__name__, kwargs))

    def add_pub(self, **kwargs):
        """
        Configure the reactor to publish on 'url'.
        """
        self.q.coro_put((AddPubCommand.__name__, kwargs))

    def remove_pub(self, **kwargs):
        """
        Close the publishing socket on 'url'
        """
        self.q.coro_put((RemovePubCommand.__name__, kwargs))

    def add_dealer(self, callback='route', **kwargs):
        """
        needs 'url', 'callback', and 'id'
        """
        kwargs['callback'] = callback
        self.q.coro_put((AddDealerCommand.__name__, kwargs))

    def add_router(self, callback='route_req', **kwargs):
        """
        needs 'url', 'callback'
        """
        kwargs['callback'] = callback
        self.q.coro_put((AddRouterCommand.__name__, kwargs))

    def request(self, timeout=0, **kwargs):
        """
        'url', 'data', 'timeout' ... must add_dealer first with the url
        Timeout is a int in miliseconds
        """
        kwargs['timeout'] = timeout
        self.q.coro_put((RequestCommand.__name__, kwargs))

    def reply(self, **kwargs):
        """
        'url', 'data', and 'id' ... must add_router first with url
        """
        self.q.coro_put((ReplyCommand.__name__, kwargs))

    def prove_im_nonblocking(self):
        self.log.debug("xD")
