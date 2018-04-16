import asyncio
import zmq.asyncio
from cilantro.logger import get_logger


# TODO add some API for hooking this stuff up programatically instead of statically defining the callbacks
SUB_CALLBACK = 'route'
DEAL_CALLBACK = 'route'
ROUTE_CALLBACK = 'route_req'
TIMEOUT_CALLBACK = 'route_timeout'


class ExecutorMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        clsobj.log = get_logger(clsobj.__name__)

        if not hasattr(clsobj, 'registry'):
            clsobj.registry = {}
        if clsobj.__name__ != 'Executor':
            clsobj.registry[clsobj.__name__] = clsobj

        return clsobj


class Executor(metaclass=ExecutorMeta):
    def __init__(self, loop, context, inproc_socket):
        self.loop = loop
        asyncio.set_event_loop(self.loop)
        self.context = context
        self.inproc_socket = inproc_socket

    async def recv_multipart(self, socket, callback, ignore_first_frame=False):
        self.log.warning("Starting recv on socket {} with callback {}".format(socket, callback))
        while True:
            multi_msg = await socket.recv_multipart()
            self.log.debug("Got multipart msg: {}".format(multi_msg))

            if ignore_first_frame:
                multi_msg = multi_msg[1:]
            self.call_on_mt(callback, *multi_msg)

    def call_on_mt(self, callback, *args):
        self.inproc_socket.send_pyobj((callback, args))


class SubPubExecutor(Executor):
    def __init__(self, loop, context, inproc_socket):
        super().__init__(loop, context, inproc_socket)
        self.sub = None
        self.pub = None

    def send_pub(self, filter, metadata, data):
        assert self.pub, "Attempted to publish data but publisher socket is not configured"
        self.pub.send_multipart([filter, metadata, data])

    def add_pub(self, url):
        if self.pub:
            self.log.error("Attempted to add publisher on url {} but publisher socket already configured.".format(url))
            return

        self.log.info("Creating publisher socket")
        self.pub = self.context.socket(socket_type=zmq.PUB)
        self.log.warning("Publishing on url {}".format(url))
        self.pub.bind(url)

    def add_sub(self, url: str, filter: str):
        if not self.sub:
            self.log.info("Creating subscriber socket")
            self.sub = self.context.socket(socket_type=zmq.SUB)
            asyncio.ensure_future(self.recv_multipart(self.sub, SUB_CALLBACK, ignore_first_frame=True))

        self.log.info("Subscribing to url {} with filter {}".format(url, filter))
        self.sub.connect(url)
        self.sub.setsockopt(zmq.SUBSCRIBE, filter.encode())

    def remove_sub(self, url: str, msg_filter: str):
        assert self.sub, "Remove sub command invoked but sub socket is not set"

        self.sub.setsockopt(zmq.UNSUBSCRIBE, msg_filter.encode())
        self.sub.disconnect(url)

    def remove_pub(self, url: str):
        # TODO -- implement
        self.log.error("remove_pub not implemented")
        raise NotImplementedError


class DealerRouterExecutor(Executor):
    def __init__(self, loop, context, inproc_socket):
        super().__init__(loop, context, inproc_socket)
        self.dealer = None
        self.router = None

    def add_router(self, url):
        assert self.router is None, "Attempted to add router socket on url {} but router socket already configured".format(url)

        self.log.info("Creating router socket on url {}".format(url))
        self.router = self.context.socket(socket_type=zmq.ROUTER)
        self.router.bind(url)
        asyncio.ensure_future(self.recv_multipart(self.router, ROUTE_CALLBACK))

    def add_dealer(self, url, id):
        if not self.dealer:
            self.log.info("Creating dealer socket with id {}".format(id))
            self.dealer = self.context.socket(socket_type=zmq.DEALER)
            self.dealer.identity = id.encode('ascii')
            asyncio.ensure_future(self.recv_multipart(self.dealer, DEAL_CALLBACK))

        self.log.info("Dealing socket connecting to url {}".format(url))
        self.dealer.connect(url)

    def request(self, url, timeout, metadata, data):
        assert self.dealer, "Attempted to make request but dealer socket is not set"
        self.log.debug("Composing request to url {}\ntimeout: {}\nmetadata: {}\ndata: {}"
                       .format(url, timeout, metadata, data))

        if timeout > 0:
            self.log.debug("Setting timeout of {} for request at url {} with data {}".format(timeout, url, data))
            # TODO -- timeout functionality

        self.dealer.send_multipart([metadata, data])

    def reply(self, url, id, metadata, data):
        assert self.router, "Attempted to reply on url {} but router socket is not set".format(url)
        self.router.send_multipart([id, metadata, data])

    def remove_router(self, url):
        # TODO -- implement
        self.log.critical("remove router not implemented")
        raise NotImplementedError

    def remove_dealer(self, url, id):
        # TODO -- implement
        self.log.critical("remove dealer not implemented")
        raise NotImplementedError