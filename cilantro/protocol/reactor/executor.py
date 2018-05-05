import asyncio, time
import zmq.asyncio
from cilantro.logger import get_logger
from cilantro.messages import ReactorCommand, Envelope

# TODO add some API for hooking this stuff up programatically instead of statically defining the callbacks
SUB_CALLBACK = 'route'
DEAL_CALLBACK = 'route'
REQ_CALLBACK = 'route_req'
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
        self.duplication = {}

    async def recv_multipart(self, socket, callback, ignore_first_frame=False):
        # self.log.warning("Starting recv on socket {} with callback {}".format(socket, callback))
        while True:
            # self.log.debug("waiting for multipart msg...")
            msg = await socket.recv_multipart()

            if ignore_first_frame:
                # assert len(msg) == 1, "ignore_first_frame is true, meaning we should get a msg of length 1 (no header)."
                header = None
            else:
                assert len(msg) == 2, "ignore_first_frame is false; Expected a multi_msg of len 2 with " \
                                      "(header, envelope) but got {}".format(msg)
                header = msg[0].decode()

            env_binary = msg[-1]
            env = Envelope.from_bytes(env_binary)
            env_meta = env.meta
            if self.duplication.get(env_meta.uuid):
                # Time difference less than 5 seconds is considered a collision or the same message
                if float(env_meta.timestamp) - float(self.duplication[env_meta.uuid]) < 5:
                    self.log.debug("skiipping duplicate env {}".format(env))
                    continue
            self.duplication[env_meta.uuid] = env_meta.timestamp
            self.log.debug('received envelope:\n{}'.format(env))
            self.call_on_mt(callback, header=header, envelope_binary=env_binary)

    def call_on_mt(self, callback, header: bytes=None, envelope_binary: bytes=None, **kwargs):
        if header:
            # TODO -- make header a convenience property or constant on reactor callback
            kwargs['header'] = header

        cmd = ReactorCommand.create_callback(callback=callback, envelope_binary=envelope_binary, **kwargs)
        # self.log.debug("Executor sending callback cmd: {}".format(cmd))
        self.inproc_socket.send(cmd.serialize())


class SubPubExecutor(Executor):
    def __init__(self, loop, context, inproc_socket):
        super().__init__(loop, context, inproc_socket)
        self.sub = None
        self.pubs = {}

    def send_pub(self, filter: str, envelope: bytes):
        assert len(self.pubs) != 0, "Attempted to publish data but publisher socket is not configured"
        for url in self.pubs:
            self.log.debug("Publishing to... {} the envelope: {}".format(url, Envelope.from_bytes(envelope)))
            # self.log.info("Publishing to... {}".format(url))
            self.pubs[url].send_multipart([filter.encode(), envelope])

    def add_pub(self, url):
        # TODO -- implement functionality so add_pub will close the existing socket and create a new one if we are switching urls
        if self.pubs.get(url):
            self.log.error("Attempted to add publisher on url {} but publisher socket already configured.".format(url))
            return

        self.log.info("Creating publisher socket on url {}".format(url))
        self.pubs[url] = self.context.socket(socket_type=zmq.PUB)
        self.pubs[url].bind(url)
        time.sleep(0.2)

    def add_sub(self, url: str, filter: str):
        if not self.sub:
            self.log.info("Creating subscriber socket")
            self.sub = self.context.socket(socket_type=zmq.SUB)
            asyncio.ensure_future(self.recv_multipart(self.sub, SUB_CALLBACK, ignore_first_frame=True))

        self.log.info("Subscribing to url {} with filter '{}'".format(url, filter))
        self.sub.connect(url)
        self.sub.setsockopt(zmq.SUBSCRIBE, filter.encode())

    def remove_sub(self, url: str, msg_filter: str):
        assert self.sub, "Remove sub command invoked but sub socket is not set"
        self.sub.setsockopt(zmq.UNSUBSCRIBE, msg_filter.encode())
        self.sub.disconnect(url)

    def remove_pub(self, url: str):
        assert self.pubs.get(url), "Remove pub command invoked but pub socket is not set"
        self.pubs[url].disconnect(url)
        self.pubs[url].close()
        del self.pubs[url]


class DealerRouterExecutor(Executor):
    def __init__(self, loop, context, inproc_socket):
        super().__init__(loop, context, inproc_socket)

        # TODO -- make a list/hash of dealer sockets
        self.dealers = {}
        self.router = None

    def add_router(self, url):
        assert self.router is None, "Attempted to add router socket on url {} but router socket already configured".format(url)

        self.log.info("Creating router socket on url {}".format(url))
        self.router = self.context.socket(socket_type=zmq.ROUTER)
        self.router.bind(url)
        asyncio.ensure_future(self.recv_multipart(self.router, REQ_CALLBACK))

    def add_dealer(self, url, id):
        assert url not in self.dealers, "Url {} already in self.dealers {}".format(url, self.dealers)
        self.log.info("Creating dealer socket for url {} with id {}".format(url, id))
        self.dealers[url] = self.context.socket(socket_type=zmq.DEALER)
        self.dealers[url].identity = id.encode('ascii')

        # TODO -- store this future so we can cancel it later
        future = asyncio.ensure_future(self.recv_multipart(self.dealers[url], DEAL_CALLBACK,
                                                           ignore_first_frame=True))

        self.log.info("Dealer socket connecting to url {}".format(url))
        self.dealers[url].connect(url)

    def request(self, url, envelope, timeout=0):
        assert url in self.dealers, "Attempted to make request to url {} that is not in self.dealers {}"\
            .format(url, self.dealers)
        timeout = int(timeout)
        self.log.debug("Composing request to url {}\ntimeout: {}\nenvelope: {}".format(url, timeout, envelope))

        if timeout > 0:
            # TODO -- timeout functionality
            pass

        self.dealers[url].send_multipart([envelope])

    def reply(self, id, envelope):
        # TODO error propgation
        # i  = 10 / 0
        # TODO are we not propagating exceptions properly? This error above does not get outputed in a test..?
        # self.log.critical("\n\n\n\n sending reply to id {} with env {} \n\n\n\n".format(id, envelope))
        assert self.router, "Attempted to reply but router socket is not set"
        self.router.send_multipart([id.encode(), envelope])

    def remove_router(self, url):
        # TODO -- implement
        self.log.critical("remove router not implemented")
        raise NotImplementedError

    def remove_dealer(self, url, id):
        # TODO -- implement
        self.log.critical("remove dealer not implemented")
        raise NotImplementedError
