import asyncio
# import zmq
import zmq.asyncio
import aioprocessing
import random
from cilantro.logger import get_logger
import time
import logging
from collections import defaultdict
from cilantro.messages import Envelope
from multiprocessing import Process

from cilantro.protocol.reactor.executor import *

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


*******************
once dynamic routing tables implemented...could be cool if on the node layer, you could access different delegates using
lists or python arrays. Like send messages to self.routing.delegate[0] or self.routing.delegate_for_vk(verifying_key) 
"""

# class ZMQLoop:
#     PUB, SUB, DEAL, ROUTE = range(4)
#     SOCKET, FUTURE, ID = range(3)
#
#     def __init__(self, parent_socket, loop, log):
#         self.log = log
#         self.parent_socket = parent_socket
#
#         self.loop = loop
#         asyncio.set_event_loop(loop)
#
#         self.sockets = defaultdict(dict)
#         self.ctx = zmq.asyncio.Context()
#
#         self.pending_reqs = {}  # key is msg uuid, value is an asyncio.Handle instance
#         self.msg_log = set()  # Set of received msg uuids, (for checking duplicate messages)
#
#     async def receive(self, socket, url, callback):
#         self.log.warning("--- Started Receiving on URL: {} with callback {} ---".format(url, callback))
#         while True:
#             self.log.debug("({}) zmqloop recv waiting for msg...".format(url))
#             msg_binary = await socket.recv()
#             self.log.debug("({}) zmqloop recv got msg: {}".format(url, msg_binary))
#
#             try:
#                 msg = self.open_msg(msg_binary)[0]
#             except Exception as e:
#                 self.log.error("Error opening msg: {}, with msg binary: {}".format(e, msg_binary))
#                 return
#             self.call_on_mt(callback, msg)
#
#     async def receive_multipart(self, socket, url, callback):
#         self.log.warning("--- Starting Receiving Multipart To URL: {} with callback {} ---".format(url, callback))
#         while True:
#             self.log.debug("({}) zmqloop recv_multipart waiting for msg...".format(url))
#             id, msg_binary = await socket.recv_multipart()
#             self.log.debug("({}) zmqloop recv_multipart got msg: {} with id: {}".format(url, msg_binary, id))
#
#             # TODO -- cleanup error handling with context managers?
#             try:
#                 msg, uuid = self.open_msg(msg_binary)
#             except Exception as e:
#                 self.log.error("Error opening msg: {}, with msg binary: {}".format(e, msg_binary))
#                 return
#             self.call_on_mt(callback, msg, url, id, uuid)
#
#     def check_timeout(self, envelope, url):
#         uuid = envelope.uuid
#         self.log.critical("Message with from url {} and msg uuid {} timed out (msg={})".format(url, uuid, envelope))
#         """
#         TODO -- we need to be opening messages as soon as we receive them and queueing them up to run on mainthread
#         instead of blocking while mainthread does stuff (as we are currently). Otherwise, we may receive a message
#         but the timeout was trigger b/c main thread did not have time to process it.
#         Thus, assertion below is really for debugging
#         """
#         assert uuid in self.pending_reqs, "UUID {} not found in pending requests {}".format(uuid, self.pending_reqs)
#
#         del self.pending_reqs[uuid]
#         self.call_on_mt(TIMEOUT_CALLBACK, envelope.open(), url)
#
#     def open_msg(self, msg_binary):
#         # Open msg
#         # TODO -- Check for duplicates
#         # Remove callback for timeout (if any)
#         # TODO -- add error handling for envelope open
#
#         envelope = Envelope.from_bytes(msg_binary)
#         msg = envelope.open()
#
#         if envelope.uuid in self.pending_reqs:
#             self.log.info("Canceling timeout callback for message with uuid {}".format(envelope.uuid))
#             self.pending_reqs[envelope.uuid].cancel()
#             del self.pending_reqs[envelope.uuid]
#
#         return msg, envelope.uuid
#
#     def call_on_mt(self, callback, *args):
#         # assert hasattr(self.parent, callback), "Callback {} not found on parent object {}" \
#         #     .format(TIMEOUT_CALLBACK, self.parent)
#         msg = "Callback < {} > with args: {}".format(callback, args)
#         self.log.critical("calling: {}".format(msg))
#
#         self.parent_socket.send_pyobj((callback, args))
#
#         # self.parent_socket.send(msg.encode())
#         # getattr(self.parent, callback)(*args)


class ReactorCore:
    READY_SIG = 'READY'
    PAUSE_SIG = 'PAUSE'

    def __init__(self, url, p_name=''):
        self.log = get_logger("{}.ReactorCore".format(p_name))
        self.log.info("ReactorCore started with url {}".format(url))
        self.url = url

        # Comment out below for more granularity in debugging
        # self.log.setLevel(logging.INFO)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)
        self.socket.connect(self.url)

        self.executors = {}
        for name, executor in Executor.registry.items():
            self.log.debug("Creating executor for name {} and class {}".format(name, executor))
            self.executors[name] = executor(self.loop, self.context, self.socket)

        self.loop.run_until_complete(self._recv_messages())

    async def _recv_messages(self):
        # Notify mainthread that this proc is ready
        self.log.debug("reactor notifying mainthread of ready")
        self.socket.send(b'LETS GO')

        self.log.warning("-- Starting Recv on PAIR Socket at {} --".format(self.url))
        while True:
            self.log.debug("Reading socket...")
            cmd = await self.socket.recv_pyobj()
            self.log.debug("Got cmd from queue: {}".format(cmd))
            self.process_cmd(cmd)

    def process_cmd(self, cmd):
        # Sanity checks (just for debugging really)
        assert type(cmd) == tuple, "Only a tuple object can be inserted into the queue"
        assert len(cmd) == 3, "Command must have 3 elements: (executor_class, executor_func, kwwargs dict)"
        executor_name, executor_func, kwargs = cmd
        assert executor_name in self.executors, "Executor name {} not found in executors {}"\
            .format(executor_name, self.executors)
        assert hasattr(self.executors[executor_name], executor_func), "Function {} not found on executor class {}"\
            .format(executor_func, self.executors[executor_name])

        # Execute command
        getattr(self.executors[executor_name], executor_func)(**kwargs)


class NetworkReactor:
    def __init__(self, parent, loop):
        self.log = get_logger("{}.NetworkReactor".format(type(parent).__name__))
        self.url = "ipc://reactor-" + str(random.randint(0, pow(2, 16)))

        # Set instance vars
        self.parent = parent
        self.loop = loop
        self.reactor = None
        asyncio.set_event_loop(self.loop)

        # Create zmq context and pair socket to communicate with reactor sub process
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)
        self.socket.bind(self.url)

        # Start reactor sub process
        self.proc = Process(target=self._start_reactor, args=(self.url, type(parent).__name__))
        self.proc.start()

        # Suspend execution of this proc until reactor proc is ready
        self.loop.run_until_complete(self._wait_child_rdy())

        # Start listening to messages from reactor proc
        asyncio.ensure_future(self._recv_messages())

    def _start_reactor(self, url, p_name):
        self.log.info("Starting ReactorCore process")
        self.reactor = ReactorCore(url=url, p_name=p_name)

    async def _wait_child_rdy(self):
        self.log.critical("Waiting for ready sig from child proc...")
        msg = await self.socket.recv()
        self.log.critical("Got ready sig from child proc: {}".format(msg))

    async def _recv_messages(self):
        self.log.warning("~~~ Starting recv for messages ~~~")
        while True:
            self.log.debug("Waiting for callback...")
            callback, args = await self.socket.recv_pyobj()
            self.log.debug("Got callback")
            getattr(self.parent, callback)(*args)

    def notify_ready(self):
        self.log.critical("NOTIFIY READY")
        # TODO -- implement (add queue of tx, flush on notify ready, pause on notify_pause

    def notify_pause(self):
        self.log.critical("NOTIFY PAUSE")
        # TODO -- implement

    def add_sub(self, callback='route', **kwargs):
        """
        Starts subscribing to 'url'.
        Requires kwargs 'url' of subscriber (as a string)...callback is optional, and by default will forward incoming messages to the
        meta router built into base node
        """
        self.log.debug("add sub")
        # kwargs['callback'] = callback
        self._send_command(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, kwargs)
        # self.q.coro_put((AddSubCommand.__name__, kwargs))

    def remove_sub(self, **kwargs):
        """
        Requires kwargs 'url' of sub
        """
        # self.socket.send(b'HERES A COMMAND')
        self._send_command(SubPubExecutor.__name__, SubPubExecutor.remove_sub.__name__, kwargs)
        # self.q.coro_put((RemoveSubCommand.__name__, kwargs))

    def pub(self, **kwargs):
        """
        Publish data 'data on socket connected to 'url'
        Requires kwargs 'url' to publish on, as well as 'data' which is the binary data (type should be bytes) to publish
        If reactor is not already set up to publish on 'url', this will be setup and the data will be published
        """
        self._send_command(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__, kwargs)
        # self.q.coro_put((SendPubCommand.__name__, kwargs))

    def add_pub(self, **kwargs):
        """
        Configure the reactor to publish on 'url'.
        """
        self.log.debug("add pub")
        self._send_command(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, kwargs)
        # self.q.coro_put((AddPubCommand.__name__, kwargs))

    def remove_pub(self, **kwargs):
        """
        Close the publishing socket on 'url'
        """
        self._send_command(SubPubExecutor.__name__, SubPubExecutor.remove_pub.__name__, kwargs)
        # self.q.coro_put((RemovePubCommand.__name__, kwargs))

    def add_dealer(self, callback='route', **kwargs):
        """
        needs 'url', 'callback', and 'id'
        """
        kwargs['callback'] = callback
        self._send_command(DealerRouterExecutor.__name__, DealerRouterExecutor.add_dealer.__name__, kwargs)
        # self.q.coro_put((AddDealerCommand.__name__, kwargs))

    def add_router(self, callback='route_req', **kwargs):
        """
        needs 'url', 'callback'
        """
        self.log.debug("add route")
        # kwargs['callback'] = callback
        self._send_command(DealerRouterExecutor.__name__, DealerRouterExecutor.add_router.__name__, kwargs)
        # self.q.coro_put((AddRouterCommand.__name__, kwargs))

    def request(self, timeout=0, **kwargs):
        """
        'url', 'data', 'timeout' ... must add_dealer first with the url
        Timeout is a int in miliseconds
        """
        self.log.debug("request")
        kwargs['timeout'] = timeout
        self._send_command(DealerRouterExecutor.__name__, DealerRouterExecutor.request.__name__, kwargs)
        # self.q.coro_put((RequestCommand.__name__, kwargs))

    def reply(self, **kwargs):
        """
        'url', 'data', and 'id' ... must add_router first with url
        """
        self._send_command(DealerRouterExecutor.__name__, DealerRouterExecutor.reply.__name__, kwargs)
        # self.socket.send_pyobj((ReplyCommand.__name__, kwargs))
        # self.q.coro_put((ReplyCommand.__name__, kwargs))

    def prove_im_nonblocking(self):
        self.log.debug("xD")

    def _send_command(self, executor_class, executor_func, kwargs):
        cmd = (executor_class, executor_func, kwargs)
        self.socket.send_pyobj(cmd)
