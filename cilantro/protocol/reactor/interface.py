import asyncio
import zmq.asyncio
from cilantro.utils import LProcess
import random
from cilantro.logger import get_logger
from cilantro.messages import ReactorCommand
from cilantro.protocol.reactor.core import ReactorCore, CHILD_RDY_SIG


class ReactorInterface:
    def __init__(self, router, loop):
        self.log = get_logger("{}.ReactorInterface".format(type(router).__name__))
        self.url = "ipc://reactor-" + str(random.randint(0, pow(2, 16)))

        # Set instance vars
        self.router = router
        self.loop = loop
        asyncio.set_event_loop(self.loop)

        # Create zmq context and pair socket to communicate with reactor sub process
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)

        self.socket.bind(self.url)

        # Start reactor sub process
        self.proc = LProcess(target=self._start_reactor, args=(self.url, type(router).__name__))
        self.proc.daemon = True
        self.proc.start()

        # Block execution of this proc until reactor proc is ready
        self.loop.run_until_complete(self._wait_child_rdy())

        # Start listening to messages from reactor proc
        asyncio.ensure_future(self._recv_messages())

    def _start_reactor(self, url, p_name):
        reactor = ReactorCore(url=url, p_name=p_name)

    async def _wait_child_rdy(self):
        self.log.debug("Waiting for ready sig from child proc...")
        msg = await self.socket.recv()
        assert msg == CHILD_RDY_SIG, "Got unexpected rdy sig from child proc (got '{}', but expected '{}')"\
            .format(msg, CHILD_RDY_SIG)
        self.log.debug("Got ready sig from child proc: {}".format(msg))

    async def _recv_messages(self):
        self.log.debug("~~ Reactor listening to messages from ReactorCore ~~")
        while True:
            # TODO refactor and pretty this up
            self.log.debug("Waiting for callback...")
            # callback, args = await self.socket.recv_pyobj()
            # args = list(args)
            msg = await self.socket.recv()

            callback = ReactorCommand.from_bytes(msg)

            self.log.debug("Got callback cmd <{}>".format(callback))

            self._run_callback(callback)

    def _run_callback(self, callback):
        self.log.debug("Running callback cmd {}".format(callback))

        # TODO -- engineer less hacky way to do this that doesnt explicitly rely on multiframe positions
        # meta, payload = args[-2:]
        # envelope = Envelope.from_bytes(payload=payload, message_meta=meta)
        # new_args = args[:-2] + [envelope]
        #
        # getattr(self.router, callback)(*new_args)

    def notify_ready(self):
        self.log.critical("NOTIFIY READY")
        # TODO -- implement (add queue of tx, flush on notify ready, pause on notify_pause

    def notify_pause(self):
        self.log.critical("NOTIFY PAUSE")
        # TODO -- implement

    def send_cmd(self, cmd: ReactorCommand):
        assert isinstance(cmd, ReactorCommand), "Only ReactorCommand instances can sent through the reactor"
        self.socket.send(cmd.serialize())

    def do_something(self, arg1='default'):
        self.log.critical("\n *** DOING SOMETHING with arg1 = {} *** \n".format(arg1))
