from cilantro.logger import get_logger
from random import random
import time

import asyncio
import zmq
import zmq.asyncio
import aioprocessing
from multiprocessing import Process, Queue
from threading import Thread

URL = "tcp://127.0.0.1:5566"


"""
NOTE -- it may be necessary to put a shared lock between reactor/main thread to enforce
synchronous callback execution

commands obviously specify new events for the reactor. They must be able to accept some callback
or on_complete type handler. If so, how to ensure that this is run on the main thread?
- Commands get put into a queue on the main thread, which is awaiting to be read in the run loop
- How to make sure callbacks wait for main thread to finish its work before they are executed?
    - IE data is read from 2 sockets at approximately the same time. Data from socket 1 gets
    - sent to its callback A (presumably on the main thread), but while callback A is busy executing
    - callback B wants to execute

Possible solution:
    - Have an internal queue of callbacks waiting to be executed inside the reactor
    - Have a lock on the reactor that is true if a callback is being executed (reactor obviosly will know when one
    - starts).

    - Or just have a loop that continuously reads from the queue and runs the callbacks on the main thread?
        - could this behavior be in an entirely separate event loop?
            - Can we really have 2 event loops running at same time?
    - When a callback finishes, run the next one


Who is responsible for the logic for creating/disconnecting/ect the sockets? Obviously there would have to be
a switch statement inside of reactor when its dealing with completing the command. Maybe the logic should just
go there and command should just be an ENUM?
    - Or, a more complex but modular solution -- each command "type" (pub/sub, or req/reply, or deal/route, ect)
      has its own state (share zmq context tho?). Then perhaps this state gets passed into the execution of
      each command. Or should there be entirely differant command objects for each one? Is ivoking them with
      these kwargs ratchet? No i think its ok for now.



There will exist long running callbacks on the main thread (maybe building merk trees, or sending lots of data)
These we would like to be async, but sometimes should only be able to be invoked once (i.e. if we are already
building a merk tree, and we get a request that triggers building a merk tree, only the first one should be run)
Who's responsbility is it to schedule this kind of behavior? Should the node itself be setting internal locks?
Or should the node be responsbile for designing flags/locks/ect. And is this even a real problem?


OR ENTIRELY DIFF IDEA:
Fuck the custom callbacks. Just have main thread pass it ONE callback in reactor's init, and run all code through
there


Is this handler approach too javascripty for python?
- NO! Javascript is build for event driven! If we are gravitating towards its style unintentionally, I say were
  on to something.

would be sick to just be like
n = Node()
n._reactor_q.put(COMMAND.SUB, url='127.0...', callback=somefunc)
n._reactor_q.put(COMMAND.PUB, url='127.0....', data=b'hi', on_complete=somfunc)



"""




"""
How to link the call signature passed into the queue to the actual proper command class?
Well, lets have each command class define their own name, i.e. 

class AddPubCommand(CommandBase):
    name = ADD_PUB
    
But then wherever the signature are be called, we must import each type of command
well I think importing these command types will be unavoidable. Just stick them in their 
own module and define the __all__ import thing in the  __init__.py 

Now, we just have the issues of dynamically adding the command class types upon creation to route the thing
without an ugly switch statement. Should be able to use metaprogramming for this
"""


"""
ATTACK PLAN

- see whats up with having multiple event loops (could these even be on the same thread? does this even make sense?)
    - or actually first lets see if we can get 2 blocking events on one eventloop

- get a queue object shared between parent thread and child (event loop) thread
- get a loop checking that queue and executing commands (just print something for each command type at first)
- Now, get another loop (or same loop) building commands to run these mfking queries mayne
- get callbacks running on main thread, and find a way to verify this
- PROFIT
"""


# should we really have all messages go through some central router? Would it not be sufficient
# to just handle messages on a callback-basis?
# we must be cognizant that people can sender whatever bytes they want in the capnp structs
# everytime we read and operate on the data, we are prone to "bit-injections" where we can
# not 100% trust the integrity of the data

class NetworkReactor(Thread):

    def __init__(self, queue):
        super().__init__()
        self.log = get_logger("ReactorInterface")
        self.queue = queue

        # Does this need to be inside run()? I think it might bruh
        self.loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        # loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)

        self.ctx, self.socket = None, None

        # self.ctx = zmq.asyncio.Context()
        # self.socket = self.ctx.socket(socket_type=zmq.SUB)
        # self.socket.setsockopt(zmq.SUBSCRIBE, b'')
        # self.socket.connect(URL)
        # Can i connect to multiple urls?

        # self.ctx, self.socket = None, None

    def run(self):
        super().run()

        self.log.debug("Run started")

        self.ctx = zmq.asyncio.Context()

        asyncio.set_event_loop(self.loop)
        # self.loop.run_until_complete(asyncio.gather(self.listen(),))
        # self.loop.run_until_complete(asyncio.gather(self.read_queue(), ))
        self.loop.run_until_complete(asyncio.gather(self.read_queue(), self.listen()))

        # BUT THIS WORKS....WHY!!?!?!?!?!?!?
        # self.loop.run_until_complete(self.listen())

    async def read_queue(self):
        self.log.debug("-- Starting Queue Listening --")
        while True:
            self.log.debug("Reading queue...")
            n = await self.queue.coro_get()
            self.log.info("Got data from queue: {}".format(n))

    async def listen(self):
        self.log.debug("-- Starting Listening --")
        self.socket = self.ctx.socket(socket_type=zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')
        self.socket.connect(URL)
        while True:
            self.log.debug("listen waiting...")
            msg = await self.socket.recv()
            self.log.debug("listen got msg: {}".format(msg))


def start_listening():
    async def listen(socket, log):
        log.debug("Starting listening...")
        log.debug("socket: {}".format(socket))
        while True:
            log.debug("listen waiting...")
            msg = await socket.recv()
            log.debug("listen got msg: {}".format(msg))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    log = get_logger("NetworkListener")

    ctx = zmq.asyncio.Context()
    socket = ctx.socket(socket_type=zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE, b'')
    socket.connect(URL)

    # loop = asyncio.get_event_loop()

    loop.run_until_complete(listen(socket, log))


"""
-- META STUFF --
"""
from inspect import Parameter, Signature


def make_signature(names):
    return Signature(
        Parameter(name, Parameter.POSITIONAL_OR_KEYWORD)
        for name in names)


class CommandMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        print("CommandMeta NEW called /w class ", cls.__name__)
        clsobj = super().__new__(cls, clsname, bases, clsdict)

        sig = make_signature(clsobj._fields)
        setattr(clsobj, '__signature__', sig)

        if not hasattr(clsobj, 'registry'):
            print("Creating Registry")
            clsobj.registry = {}
        print("Adding to registry: ", clsobj.__name__)
        clsobj.registry[clsobj.__name__] = clsobj

        return clsobj


class Command(metaclass=CommandMeta):
    _fields = []
    def __init__(self, *args, **kwargs):
        bound = self.__signature__.bind(*args, **kwargs)
        for name, val in bound.arguments.items():
            setattr(self, name, val)

    @classmethod
    def execute(cls, ):


class AddSubCommand(Command):
    _fields = ['url', 'callback']


class RemoveSubCommand(Command):
    _fields = ['url']


# if __name__ == "__main__":
#     log = get_logger("Main")
#     q = aioprocessing.AioQueue()
#     reactor = ReactorInterface(queue=q)
#     reactor.start()
#
#     q.coro_put("Hi This Is An Item")

    # sub = Sub()
    # time.sleep(16)
    # print("done")

    # q = Queue()
    # print("starting main")
    # nr = NetworkingReactor(queue=q)
    # nr.start()
    # print("is this unblocked?")
    # print("sleeping...")
    # time.sleep(20)
    # print("done sleeping")

    # log.debug("Starting (main thread here)")
    # listener = Thread(target=start_listening)
    # listener.daemon = True
    # listener.start()
    # log.debug("can this be seen?")

    # time.sleep(100)

class ReactorCore(Thread):

    def __init__(self, queue, parent):
        super().__init__()
        self.log = get_logger("Reactor")

        # Comment out below for more granularity in debugging
        # self.log.setLevel(logging.INFO)

        self.queue = queue
        self.parent = parent
        self.parent_ready = False
        self.cmd_queue = []

        # Is this really the right way to do Thread subclassing? Having to instantiate all ur stuff in the run() method
        # feels low key ratchet

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)


        self.sockets, self.ctx = None, None

    def run(self):
        super().run()
        self.log.debug("ReactorDaemon Run started")

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
        if cmd.type == Command.READY:
            self.log.debug("Setting parent_ready to True...flushing {} cmds".format(len(self.cmd_queue)))
            self.parent_ready = True
            self.cmd_queue.reverse()
            while len(self.cmd_queue) > 0:
                c = self.cmd_queue.pop()
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