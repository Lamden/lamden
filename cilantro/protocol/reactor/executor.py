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

    def send_pub(self, url, filter, metadata, data):
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

    def add_sub(self, url: str, msg_filter: str):
        if not self.sub:
            self.log.info("Creating subscriber socket")
            self.sub = self.context.socket(socket_type=zmq.SUB)
            asyncio.ensure_future(self.recv_multipart(self.sub, SUB_CALLBACK, ignore_first_frame=True))

        self.log.info("Subscribing to url {} with filter {}".format(url, msg_filter))
        self.sub.connect(url)
        self.sub.setsockopt(zmq.SUBSCRIBE, msg_filter.encode())

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



# class AddSubCommand(Command):
#     @classmethod
#     def execute(cls, zl: ZMQLoop, url, callback):
#         assert url not in zl.sockets[ZMQLoop.SUB], \
#             "Subscriber already exists for that socket (sockets={})".format(zl.sockets)
#
#         socket = zl.ctx.socket(socket_type=zmq.SUB)
#         cls.log.debug("created socket {} at url {}".format(socket, url))
#         socket.setsockopt(zmq.SUBSCRIBE, b'')
#         socket.connect(url)
#         future = asyncio.ensure_future(zl.receive(socket, url, callback))
#
#         zl.sockets[ZMQLoop.SUB][url] = {}
#         zl.sockets[ZMQLoop.SUB][url][ZMQLoop.SOCKET] = socket
#         zl.sockets[ZMQLoop.SUB][url][ZMQLoop.FUTURE] = future
#
#
# class RemoveSubCommand(Command):
#     @classmethod
#     def execute(cls, zl: ZMQLoop, url):
#         assert url in zl.sockets[ZMQLoop.SUB], "Cannot remove publisher socket {} not in sockets={}" \
#             .format(url, zl.sockets)
#
#         cls.log.warning("--- Unsubscribing to URL {} ---".format(url))
#         zl.sockets[ZMQLoop.SUB][url][ZMQLoop.FUTURE].cancel()
#         zl.sockets[ZMQLoop.SUB][url][ZMQLoop.SOCKET].close()
#         zl.sockets[ZMQLoop.SUB][url][ZMQLoop.SOCKET] = None
#
#
# class AddPubCommand(Command):
#     @classmethod
#     def execute(cls, zl: ZMQLoop, url):
#         assert url not in zl.sockets[ZMQLoop.PUB], "Cannot add publisher {} that already exists in sockets {}" \
#             .format(url, zl.sockets)
#
#         cls.log.warning("-- Adding publisher {} --".format(url))
#         zl.sockets[ZMQLoop.PUB][url] = {}
#         socket = zl.ctx.socket(socket_type=zmq.PUB)
#         socket.bind(url)
#         zl.sockets[ZMQLoop.PUB][url][ZMQLoop.SOCKET] = socket
#
#         # TODO -- fix hack to solve late joiner syndrome. Read CH 2 of ZMQ Guide for real solution
#         time.sleep(0.2)
#
#
# class RemovePubCommand(Command):
#     @classmethod
#     def execute(cls, zl: ZMQLoop, url):
#         assert url in zl.sockets[ZMQLoop.PUB], "Cannot remove publisher socket {} not in sockets={}" \
#             .format(url, zl.sockets)
#         zl.sockets[ZMQLoop.PUB][url][ZMQLoop.SOCKET].close()
#         zl.sockets[ZMQLoop.PUB][url][ZMQLoop.SOCKET] = None
#         del zl.sockets[ZMQLoop.PUB][url]
#
#
# class SendPubCommand(Command):
#     @classmethod
#     def execute(cls, zl: ZMQLoop, url, data):
#         assert url in zl.sockets[ZMQLoop.PUB], "URL {} not found in sockets {}".format(url, zl.sockets)
#         assert type(data) is Envelope, "Must pass envelope type to send commands"
#         zl.log.debug("Publishing data {} to url {}".format(data, url))
#
#         zl.sockets[ZMQLoop.PUB][url][ZMQLoop.SOCKET].send(data.serialize())
#
#
# class AddDealerCommand(Command):
#     @classmethod
#     def execute(cls, zl: ZMQLoop, url, callback, id):
#         # TODO -- assert we havnt added this dealer already
#         socket = zl.ctx.socket(socket_type=zmq.DEALER)
#         socket.identity = id.encode('ascii')
#         socket.connect(url)
#         cls.log.debug("Dealer socket {} created with url {} and identity {}".format(socket, url, id))
#         future = asyncio.ensure_future(zl.receive(socket, url, callback))
#
#         zl.sockets[ZMQLoop.DEAL][url] = {}
#         zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.SOCKET] = socket
#         zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.FUTURE] = future
#         zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.ID] = id
#
#
# class AddRouterCommand(Command):
#     @classmethod
#     def execute(cls, zl: ZMQLoop, url, callback):
#         socket = zl.ctx.socket(socket_type=zmq.ROUTER)
#         socket.bind(url)
#         cls.log.debug("Router socket {} created at url {}".format(socket, url))
#         future = asyncio.ensure_future(zl.receive_multipart(socket, url, callback))
#
#         zl.sockets[ZMQLoop.ROUTE][url] = {}
#         zl.sockets[ZMQLoop.ROUTE][url][ZMQLoop.SOCKET] = socket
#         zl.sockets[ZMQLoop.ROUTE][url][ZMQLoop.FUTURE] = future
#
#
# class RequestCommand(Command):
#     @classmethod
#     def execute(cls, zl: ZMQLoop, url, data, timeout):
#         cls.log.debug("Sending request with data {} to url {} with timeout {}".format(data, url, timeout))
#         assert type(data) is Envelope, "Must pass envelope type to send commands"
#         assert data.uuid not in zl.pending_reqs, "UUID {} for envelope {} already in pending requests {}"\
#                                                  .format(data.uuid, data, zl.pending_reqs)
#         assert url in zl.sockets[ZMQLoop.DEAL], 'Tried to make a request to url {} that was not in dealer sockets {}'\
#                                                 .format(url, zl.sockets[ZMQLoop.DEAL])
#
#         if timeout > 0:
#             cls.log.info("Adding timeout of {} seconds for request with uuid {} and data {}"
#                              .format(timeout, data.uuid, data))
#             handle = zl.loop.call_later(timeout, zl.check_timeout, data, url)
#             zl.pending_reqs[data.uuid] = handle
#
#         # zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.SOCKET].send(data)
#         zl.sockets[ZMQLoop.DEAL][url][ZMQLoop.SOCKET].send_multipart([data.serialize()])
#
#
# class ReplyCommand(Command):
#     @classmethod
#     def execute(cls, zl: ZMQLoop, url, data, id):
#         assert type(data) is Envelope, "Must pass envelope type to send commands"
#         assert url in zl.sockets[ZMQLoop.ROUTE], 'Cannot reply to url {} that is not in router sockets {}'\
#             .format(url, zl.sockets[ZMQLoop.ROUTE])
#         cls.log.debug("Replying to url {} with id {} and data {}".format(url, id, data))
#         zl.sockets[ZMQLoop.ROUTE][url][ZMQLoop.SOCKET].send_multipart([id, data.serialize()])