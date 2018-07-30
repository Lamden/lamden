from cilantro import Constants
from cilantro.logger import get_logger
from cilantro.messages import ReactorCommand, Envelope
from collections import defaultdict
from cilantro.protocol.structures import CappedSet, EnvelopeAuth
import traceback, os
from cilantro.protocol.statemachine import StateInput
from cilantro.utils import IPUtils
from cilantro.protocol.overlay.dht import DHT
import asyncio, time
import zmq.asyncio

from typing import Union
import types

# Internal constants (used as keys)
_SOCKET = 'socket'
_HANDLER = 'handler'


class ExecutorMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        # clsobj.log = get_logger(clsobj.__name__)

        if not hasattr(clsobj, 'registry'):
            clsobj.registry = {}

        if clsobj.__name__ != 'Executor':  # Exclude Executor base class
            clsobj.registry[clsobj.__name__] = clsobj

        return clsobj


class Executor(metaclass=ExecutorMeta):

    _recently_seen = CappedSet(max_size=Constants.Protocol.DupeTableSize)
    _parent_name = 'ReactorDaemon'  # used for log names

    def __init__(self, loop, context, inproc_socket, ironhouse):
        self.loop = loop
        asyncio.set_event_loop(self.loop)
        self.context = context
        self.inproc_socket = inproc_socket
        self.ironhouse = ironhouse
        self.log = get_logger("{}.{}".format(Executor._parent_name, type(self).__name__))

    def add_listener(self, listener_fn, *args, **kwargs):
        # listener_fn must be a coro
        self.log.info("add_listener scheduling future {} with args {} and kwargs {}".format(listener_fn, args, kwargs))
        return asyncio.ensure_future(self._listen(listener_fn, *args, **kwargs))

    async def _listen(self, listener_fn, *args, **kwargs):
        self.log.info("_listen called with fn {}, and args={}, kwargs={}".format(listener_fn, args, kwargs))

        try:
            await listener_fn(*args, **kwargs)
        except Exception as e:
            delim_line = '!' * 64
            err_msg = '\n\n' + delim_line + '\n' + delim_line
            err_msg += '\n ERROR CAUGHT IN LISTENER FUNCTION {}\ncalled \w args={}\nand kwargs={}\n'\
                        .format(listener_fn, args, kwargs)
            err_msg += '\nError Message: '
            err_msg += '\n\n{}'.format(traceback.format_exc())
            err_msg += '\n' + delim_line + '\n' + delim_line
            self.log.error(err_msg)

    async def recv_multipart(self, socket, callback_fn: types.MethodType, ignore_first_frame=False):
        self.log.warning("--- Starting recv on socket {} with callback_fn {} ---".format(socket, callback_fn))
        while True:
            self.log.debug("waiting for multipart msg...")

            try:
                msg = await socket.recv_multipart()
            except asyncio.CancelledError:
                self.log.info("Socket cancelled: {}".format(socket))
                socket.close()
                break

            self.log.debug("Got multipart msg: {}".format(msg))

            if ignore_first_frame:
                header = None
            else:
                assert len(msg) == 2, "Expected 2 frames (header, envelope) but got {}".format(msg)
                header = msg[0].decode()

            env_binary = msg[-1]
            env = self._validate_envelope(envelope_binary=env_binary, header=header)

            if not env:
                continue

            Executor._recently_seen.add(env.meta.uuid)

            callback_fn(header=header, envelope=env)

    def call_on_mp(self, callback: str, header: str=None, envelope_binary: bytes=None, **kwargs):
        if header:
            kwargs['header'] = header

        cmd = ReactorCommand.create_callback(callback=callback, envelope_binary=envelope_binary, **kwargs)

        # self.log.critical("\ncalling callback cmd to reactor interface: {}".format(cmd))  # DEBUG line remove this

        self.inproc_socket.send(cmd.serialize())

        # self.log.critical("command sent: {}".format(cmd))  # DEBUG line, remove this later

    def _validate_envelope(self, envelope_binary: bytes, header: str) -> Union[None, Envelope]:
        # TODO return/raise custom exceptions in this instead of just logging stuff and returning none

        # Deserialize envelope
        env = None
        try:
            env = Envelope.from_bytes(envelope_binary)
        except Exception as e:
            self.log.error("Error deserializing envelope: {}".format(e))
            return None

        # Check seal
        if not env.verify_seal():
            self.log.error("Seal could not be verified for envelope {}".format(env))
            return None

        # If header is not none (meaning this is a ROUTE msg with an ID frame), then verify that the ID frame is
        # the same as the vk on the seal
        if header and (header != env.seal.verifying_key):
            self.log.error("Header frame {} does not match seal's vk {}\nfor envelope {}"
                           .format(header, env.seal.verifying_key, env))
            return None

        # Make sure we haven't seen this message before
        if env.meta.uuid in Executor._recently_seen:
            self.log.debug("Duplicate envelope detect with UUID {}. Ignoring.".format(env.meta.uuid))
            return None

        # TODO -- checks timestamp to ensure this envelope is recv'd in a somewhat reasonable time (within N seconds)

        # If none of the above checks above return None, this envelope should be good
        return env

    def teardown(self):
        raise NotImplementedError


class SubPubExecutor(Executor):
    def __init__(self, loop, context, inproc_socket, *args, **kwargs):
        super().__init__(loop, context, inproc_socket, *args, **kwargs)
        self.subs = defaultdict(dict)  # Subscriber socket
        self.pubs = {}  # Key is url, value is Publisher socket

    def _recv_pub_env(self, header: str, envelope: Envelope):
        self.log.debug("Recv'd pub envelope with header {} and env {}".format(header, envelope))
        self.call_on_mp(callback=StateInput.INPUT, envelope_binary=envelope.serialize())

    # TODO -- is looping over all pubs ok?
    def send_pub(self, filter: str, envelope: bytes):
        assert isinstance(filter, str), "'id' arg must be a string"
        assert isinstance(envelope, bytes), "'envelope' arg must be bytes"
        assert len(self.pubs) > 0, "Attempted to publish data but publisher socket(s) is not configured"

        for url in self.pubs:
            self.log.debug("Publishing to URL {} with envelope: {}".format(url, Envelope.from_bytes(envelope)))
            # self.log.info("Publishing to... {}".format(url))
            self.pubs[url].send_multipart([filter.encode(), envelope])

    def add_pub(self, url: str):
        assert url not in self.pubs, "Attempted to add pub on url that is already in self.pubs"

        self.log.info("Creating publisher socket on url {}".format(url))
        self.pubs[url] = self.ironhouse.secure_socket(
            self.context.socket(socket_type=zmq.PUB))
        # self.pubs[url] = self.context.socket(socket_type=zmq.PUB)
        self.pubs[url].bind(url)
        time.sleep(0.2)

    def add_sub(self, url: str, filter: str, vk: str):
        assert isinstance(filter, str), "'filter' arg must be a string"
        assert vk != self.ironhouse.vk, "Cannot subscribe to your own VK"

        if url not in self.subs:
            self.log.info("Creating subscriber socket to {}".format(url))

            curve_serverkey = self.ironhouse.vk2pk(vk)
            # self.subs[url]['socket'] = socket = self.context.socket(socket_type=zmq.SUB)
            self.subs[url]['socket'] = socket = self.ironhouse.secure_socket(
                self.context.socket(socket_type=zmq.SUB),
                curve_serverkey=curve_serverkey)
            socket.connect(url)
            self.subs[url]['filters'] = []

        if filter not in self.subs[url]['filters']:
            self.log.debug("Adding filter {} to sub socket at url {}".format(filter, url))
            self.subs[url]['filters'].append(filter)
            self.subs[url]['socket'].setsockopt(zmq.SUBSCRIBE, filter.encode())

        if not self.subs[url].get('future'):
            self.log.debug("Starting listener event for subscriber socket at url {}".format(url))
            self.subs[url]['future'] = self.add_listener(self.recv_multipart,
                                                 socket=self.subs[url]['socket'],
                                                 callback_fn=self._recv_pub_env,
                                                 ignore_first_frame=True)

    def remove_sub(self, url: str):
        assert url in self.subs, "Attempted to remove a sub that was not registered in self.subs"
        self.subs[url]['future'].cancel()  # socket is closed in the asyncio.cancelled
        del self.subs[url]

    def remove_sub_filter(self, url: str, filter: str):
        assert isinstance(filter, str), "'filter' arg must be a string"
        assert url in self.subs, "Attempted to remove a sub that was not registered in self.subs"
        assert filter in self.subs[url]['filters'], "Attempted to remove a filter that was not associated with the url"
        self.subs[url]['filters'].remove(filter)
        if len(self.subs[url]['filters']) == 0:
            self.remove_sub(url)
        else:
            self.subs[url]['socket'].setsockopt(zmq.UNSUBSCRIBE, filter.encode())

    def remove_pub(self, url: str):
        assert url in self.pubs, "Remove pub command invoked but pub socket is not set"

        self.pubs[url].disconnect(url)
        self.pubs[url].close()
        del self.pubs[url]

    def teardown(self):
        for url in self.subs.copy():
            self.remove_sub(url)
        for url in self.pubs.copy():
            self.remove_pub(url)


class DealerRouterExecutor(Executor):
    def __init__(self, loop, context, inproc_socket, *args, **kwargs):
        super().__init__(loop, context, inproc_socket, *args, **kwargs)

        # 'dealers' is a simple nested dict for holding sockets by URL as well as their associated recv handlers
        # key for 'dealers' is socket URL, and value is another dict with keys 'socket' (value is Socket instance)
        # and 'socket' (value is asyncio handler instance)
        self.dealers = defaultdict(dict)

        self.expected_replies = {}  # Dict where key is reply UUID and value is the asyncio timeout handler

        # Router socket and recv handler
        self.router = None
        self.router_handler = None

    def _recv_request_env(self, header: str, envelope: Envelope):
        self.log.debug("Recv REQUEST envelope with header {} and envelope {}".format(header, envelope))
        self.call_on_mp(callback=StateInput.REQUEST, header=header, envelope_binary=envelope.serialize())

    def _recv_reply_env(self, header: str, envelope: Envelope):
        self.log.debug("Recv REPLY envelope with header {} and envelope {}".format(header, envelope))

        reply_uuid = envelope.meta.uuid
        if reply_uuid in self.expected_replies:
            self.log.debug("Removing reply with uuid {} from expected replies".format(reply_uuid))
            self.expected_replies[reply_uuid].cancel()
            del(self.expected_replies[reply_uuid])

        self.call_on_mp(callback=StateInput.INPUT, header=header, envelope_binary=envelope.serialize())

    def _timeout(self, url: str, request_envelope: bytes, reply_uuid: int):
        assert reply_uuid in self.expected_replies, "Timeout triggered but reply_uuid was not in expected_replies"
        self.log.info("Request to url {} timed out! reply uuid {}".format(url, reply_uuid))
        self.log.debug("Request envelope: {}".format(request_envelope))

        del(self.expected_replies[reply_uuid])
        self.call_on_mp(callback=StateInput.TIMEOUT, envelope_binary=request_envelope)

    def add_router(self, url: str):
        assert self.router is None, "Attempted to add router on url {} but socket already configured".format(url)

        self.log.info("Creating router socket on url {}".format(url))
        # self.router = self.context.socket(socket_type=zmq.ROUTER)
        self.router = self.ironhouse.secure_socket(
            self.context.socket(socket_type=zmq.ROUTER))
        self.router.bind(url)

        self.router_handler = self.add_listener(self.recv_multipart, socket=self.router,
                                                callback_fn=self._recv_request_env)

    def add_dealer(self, url: str, id: str, vk: str):
        assert vk != self.ironhouse.vk, "Cannot subscribe to your own VK"
        if url in self.dealers:
            self.log.warning("Attempted to add dealer {} that is already in self.dealers".format(url))
            return
        # assert url not in self.dealers, "Url {} already in self.dealers {}".format(url, self.dealers)

        assert isinstance(id, str), "'id' arg must be a string"
        self.log.info("Creating dealer socket for url {} with id {}".format(url, id))

        curve_serverkey = self.ironhouse.vk2pk(vk)
        self.log.debug('{}: add_dealer for url: {}'.format(os.getenv('HOST_IP'), url))
        # socket = self.context.socket(socket_type=zmq.DEALER)
        socket = self.ironhouse.secure_socket(
            self.context.socket(socket_type=zmq.DEALER),
            curve_serverkey=curve_serverkey)

        socket.identity = id.encode('ascii')

        self.log.info("Dealer socket connecting to url {}".format(url))
        socket.connect(url)

        future = self.add_listener(self.recv_multipart, socket=socket, callback_fn=self._recv_reply_env,
                                   ignore_first_frame=True)

        self.dealers[url][_SOCKET] = socket
        self.dealers[url][_HANDLER] = future

    # TODO pass in the intended replier's vk so we can be sure the reply we get is actually from him
    def request(self, url: str, reply_uuid: str, envelope: bytes, timeout=0):
        self.log.debug("requesting /w reply uuid {} and env {}".format(reply_uuid, envelope))
        assert url in self.dealers, "Attempted to make request to url {} that is not in self.dealers {}"\
            .format(url, self.dealers)
        assert isinstance(envelope, bytes), "'envelope' arg must be bytes"

        reply_uuid = int(reply_uuid)
        timeout = float(timeout)

        self.log.debug("Composing request to url {}\ntimeout: {}\nenvelope: {}".format(url, timeout, envelope))

        if timeout > 0:
            assert reply_uuid not in self.expected_replies, "Reply UUID is already in expected replies"
            self.log.debug("Adding timeout of {} for reply uuid {}".format(timeout, reply_uuid))
            self.expected_replies[reply_uuid] = self.loop.call_later(timeout, self._timeout, url, envelope, reply_uuid)

        self.dealers[url][_SOCKET].send_multipart([envelope])

    def reply(self, id: str, envelope: bytes):
        assert self.router, "Attempted to reply but router socket is not set"
        assert isinstance(id, str), "'id' arg must be a string"
        assert isinstance(envelope, bytes), "'envelope' arg must be bytes"

        self.router.send_multipart([id.encode(), envelope])

    def remove_router(self):
        assert self.router, "Tried to remove router but self.router is not set"

        self.router_handler.cancel()
        # self.log.info("Removing router at url {}".format(url))

    def remove_dealer(self, url, id=''):
        assert url in self.dealers, "Attempted to remove dealer url {} that is not in list of dealers {}"\
            .format(url, self.dealers)

        self.log.info("Removing dealer at url {} with id {}".format(url, id))

        socket = self.dealers[url][_SOCKET]
        future = self.dealers[url][_HANDLER]

        # Clean up socket and cancel future
        future.cancel()

        # 'destroy' references to socket/future (not sure if this is necessary tbh)
        self.dealers[url][_SOCKET] = None
        self.dealers[url][_HANDLER] = None
        del(self.dealers[url])

    def teardown(self):
        for url in self.dealers.copy():
            self.remove_dealer(url)
        if self.router:
            self.remove_router()
