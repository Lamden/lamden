import asyncio
import zmq.asyncio
import random
from cilantro.logger import get_logger
from cilantro.messages import MessageMeta, MessageBase, Envelope, ReactorCommand
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

CHILD_RDY_SIG = b'HEY ITS ME CHILD PROC -- LETS DO THIS MY GUY'

class ReactorCore:
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

        # self.executors = {}
        # for name, executor in Executor.registry.items():
        #     self.log.debug("Creating executor for name {} and class {}".format(name, executor))
        #     self.executors[name] = executor(self.loop, self.context, self.socket)
        self.executors = {name: executor(self.loop, self.context, self.socket)
                          for name, executor in Executor.registry.items()}

        self.loop.run_until_complete(self._recv_messages())

    async def _recv_messages(self):
        # Notify mainthread that this proc is ready
        self.log.debug("reactor notifying mainthread of ready")
        self.socket.send(CHILD_RDY_SIG)

        self.log.warning("-- Starting Recv on PAIR Socket at {} --".format(self.url))
        while True:
            self.log.debug("Reading socket...")
            cmd_bin = await self.socket.recv()
            self.log.debug("Got cmd from queue: {}".format(cmd_bin))

            try:
                cmd = ReactorCommand.from_bytes(cmd_bin)
                self.execute_cmd(cmd)
            except Exception as e:
                self.log.error("Error deserializing ReactorCommand: {}\n with command binary: {}".format(e, cmd_bin))

    def execute_cmd(self, cmd):
        self.log.debug("Executing cmd: {}".format(cmd))
        executor_name = cmd.class_name
        executor_func = cmd.func_name
        kwargs = cmd.kwargs

        if cmd.data:
            kwargs['data'] = cmd.data
        if cmd.metadata:
            kwargs['metadata'] = cmd.metadata

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
        self.log.debug("Waiting for ready sig from child proc...")
        msg = await self.socket.recv()
        self.log.debug("Got ready sig from child proc: {}".format(msg))

    async def _recv_messages(self):
        self.log.debug("~~ Starting recv for messages ~~")
        while True:
            # TODO refactor and pretty this up
            self.log.debug("Waiting for callback...")
            callback, args = await self.socket.recv_pyobj()
            self.log.debug("Got callback {} with args {}".format(callback, args))

            other_args = args[:-2]
            meta, payload = args[-2:]
            envelope = Envelope.from_bytes(payload=payload, message_meta=meta)
            new_args = args[:-2] + [envelope]
            self.log.debug("new args with envelope created: {}".format(args))

            getattr(self.parent, callback)(*new_args)

    def send_cmd(self, cmd: ReactorCommand):
        assert isinstance(cmd, ReactorCommand), "Only ReactorCommand instances can sent through the reactor"
        self.socket.send(cmd.serialize())

    def notify_ready(self):
        self.log.critical("NOTIFIY READY")
        # TODO -- implement (add queue of tx, flush on notify ready, pause on notify_pause

    def notify_pause(self):
        self.log.critical("NOTIFY PAUSE")
        # TODO -- implement

    def add_sub(self, url: str, filter: str):
        """
        Starts subscribing to 'url'.
        Requires kwargs 'url' of subscriber (as a string)...callback is optional, and by default will forward incoming messages to the
        meta router built into base node
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=url, filter=filter)
        self.socket.send(cmd.serialize())

    def remove_sub(self, url: str, msg_filter: str):
        """
        Requires kwargs 'url' of sub
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.remove_sub.__name__, url=url, filter=msg_filter)
        self.socket.send(cmd.serialize())

    def pub(self, url: str, msg_filter: str, envelope: Envelope):
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__, url=url,
                                    filter=msg_filter, data=envelope.data, metadata=envelope.metadata)

    # def pub(self, url: str, filter: str, metadata: MessageMeta, data: MessageBase):
    #     """
    #     Publish data 'data on socket connected to 'url'
    #     Requires kwargs 'url' to publish on, as well as 'data' which is the binary data (type should be bytes) to publish
    #     If reactor is not already set up to publish on 'url', this will be setup and the data will be published
    #     """
    #     cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__, url=url, filter=filter,
    #                                 data=data, metadata=metadata)
    #     self.socket.send(cmd.serialize())

    def add_pub(self, url: str):
        """
        Configure the reactor to publish on 'url'.
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=url)
        self.socket.send(cmd.serialize())

    def remove_pub(self, url: str):
        """
        Close the publishing socket on 'url'
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.remove_pub.__name__, url=url)
        self.socket.send(cmd.serialize())

    def add_dealer(self, url: str, id):
        """
        needs 'url', 'callback', and 'id'
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.add_dealer.__name__, url=url, id=id)
        self.socket.send(cmd.serialize())

    def add_router(self, url: str):
        """
        needs 'url', 'callback'
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.add_router.__name__, url=url)
        self.socket.send(cmd.serialize())

    def request(self, url: str, metadata: MessageMeta, data: MessageBase, timeout=0):
        """
        'url', 'data', 'timeout' ... must add_dealer first with the url
        Timeout is a int in miliseconds
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.request.__name__, url=url,
                                    metadata=metadata, data=data, timeout=timeout)
        self.socket.send(cmd.serialize())

    def reply(self, url: str, id: str, metadata: MessageMeta, data: MessageBase):
        """
        'url', 'data', and 'id' ... must add_router first with url
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.reply.__name__, url=url, id=id,
                                    metadata=metadata, data=data)
        self.socket.send(cmd.serialize())
