import asyncio
import zmq.asyncio
from multiprocessing import Process
import random
from cilantro.logger import get_logger
from cilantro.messages import MessageMeta, MessageBase, Envelope, ReactorCommand
from cilantro.protocol.reactor.core import ReactorCore, CHILD_RDY_SIG
from cilantro.protocol.reactor.executor import *


class Tester:
    def __init__(self):
        self.log = get_logger("NetworkReactor.Tester")

    def do_something(self):
        self.log.critical("tester is doing something")


class NetworkReactor:
    def __init__(self, parent, loop):
        self.log = get_logger("{}.NetworkReactor".format(type(parent).__name__))
        self.url = "ipc://reactor-" + str(random.randint(0, pow(2, 16)))

        # DEBUG
        self.tester = Tester()
        # self.log.critical("destruction!!!")
        # i = 10 / 0
        # END DEBUG

        # Set instance vars
        self.parent = parent
        self.loop = loop
        self.reactor = None
        asyncio.set_event_loop(self.loop)

        # Create zmq context and pair socket to communicate with reactor sub process
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.PAIR)
        self.socket.bind(self.url)

        # DEBUG TODO REMOVE THIS
        # THIS OUTPUTS
        # self.log.critical("check 1 about to die")
        # i = 10 / 0

        # Start reactor sub process
        self.proc = Process(target=self._start_reactor, args=(self.url, type(parent).__name__))
        self.proc.start()

        # DEBUG TODO REMOVE THIS
        # TODO THIS DOES NOT OUTPUT!!!!!!!!!!
        self.log.critical("\n\ncheck 2 about to die\n\n")
        i = 10 / 0

        # Block execution of this proc until reactor proc is ready
        self.loop.run_until_complete(self._wait_child_rdy())

        # DEBUG TODO REMOVE THIS
        # self.log.critical("check 3 about to die")
        # i = 10 / 0

        # Start listening to messages from reactor proc
        asyncio.ensure_future(self._recv_messages())

        # DEBUG TODO REMOVE THIS
        # self.log.critical("check 4 about to die")
        # i = 10 / 0

    def _start_reactor(self, url, p_name):
        log = get_logger("ReactorCore Target")
        log.info("Starting ReactorCore process")

        #0.5debug TODO remove
        # THIS DOES OUTPUT
        # log.critical("finna destruct")
        # i = 10 / 0

        reactor = ReactorCore(url=url, p_name=p_name)

        log.critical("\n\n\nthis will never print right\n\n\n")

    async def _wait_child_rdy(self):
        self.log.debug("Waiting for ready sig from child proc...")
        msg = await self.socket.recv()
        self.log.debug("Got ready sig from child proc: {}".format(msg))

    async def _recv_messages(self):
        self.log.debug("~~ Reactor listening to messages from ReactorCore ~~")
        while True:
            # TODO refactor and pretty this up
            self.log.debug("Waiting for callback...")
            callback, args = await self.socket.recv_pyobj()
            args = list(args)
            self.log.debug("Got callback <{}> with args {}".format(callback, args))

            self._run_callback(callback, args)
            # TODO -- engineer less hacky way to do this that doesnt explicitly rely on multiframe positions
            # other_args = args[:-2]
            # meta, payload = args[-2:]
            # envelope = Envelope.from_bytes(payload=payload, message_meta=meta)
            # new_args = args[:-2] + [envelope]
            #
            # getattr(self.parent, callback)(*new_args)

    def _run_callback(self, callback, args):
        self.log.debug("Running callback '{}' with args {}".format(callback, args))

        # TODO -- engineer less hacky way to do this that doesnt explicitly rely on multiframe positions
        meta, payload = args[-2:]
        envelope = Envelope.from_bytes(payload=payload, message_meta=meta)
        new_args = args[:-2] + [envelope]

        getattr(self.parent, callback)(*new_args)

    def _send_cmd(self, cmd: ReactorCommand):
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
        self._send_cmd(cmd)

    def remove_sub(self, url: str, filter: str):
        """
        Requires kwargs 'url' of sub
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.remove_sub.__name__, url=url, filter=filter)
        self._send_cmd(cmd)

    def pub(self, filter: str, envelope: Envelope):
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__,
                                    filter=filter, data=envelope.data, metadata=envelope.metadata)
        self.log.critical("\n\n(SEND PUB -- ABOUT TO SEND CMD: {}\n\n".format(cmd))
        self._send_cmd(cmd)

    def add_pub(self, url: str):
        """
        Configure the reactor to publish on 'url'.
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=url)
        self._send_cmd(cmd)

    def remove_pub(self, url: str):
        """
        Close the publishing socket on 'url'
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.remove_pub.__name__, url=url)
        self._send_cmd(cmd)

    def add_dealer(self, url: str, id):
        """
        needs 'url', 'callback', and 'id'
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.add_dealer.__name__, url=url, id=id)
        self._send_cmd(cmd)

    def add_router(self, url: str):
        """
        needs 'url', 'callback'
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.add_router.__name__, url=url)
        self._send_cmd(cmd)

    def request(self, url: str, metadata: MessageMeta, data: MessageBase, timeout=0):
        # TODO -- implement support for envelope
        """
        'url', 'data', 'timeout' ... must add_dealer first with the url
        Timeout is a int in miliseconds
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.request.__name__, url=url,
                                    metadata=metadata, data=data, timeout=timeout)
        self._send_cmd(cmd)

    def reply(self, url: str, id: str, metadata: MessageMeta, data: MessageBase):
        # TODO -- implement support for envelope
        """
        'url', 'data', and 'id' ... must add_router first with url
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.reply.__name__, url=url, id=id,
                                    metadata=metadata, data=data)
        self._send_cmd(cmd)

    def do_something(self, arg1='default'):
        self.log.critical("\n *** DOING SOMETHING with arg1 = {} *** \n".format(arg1))
