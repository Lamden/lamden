from cilantro import Constants
from cilantro.logger import get_logger
from cilantro.messages import ReactorCommand, Envelope
from collections import defaultdict
from cilantro.protocol.structures import CappedSet, EnvelopeAuth

import asyncio, time
import zmq.asyncio

from typing import Union
import types


# Callbacks for routing incoming envelopes back to the application layer
ROUTE_CALLBACK = 'route'
ROUTE_REQ_CALLBACK = 'route_req'
ROUTE_TIMEOUT_CALLBACK = 'route_timeout'


# Internal constants (used as keys)
_SOCKET = 'socket'
_HANDLER = 'handler'

from kademlia.network import Server
"""
Can i store the futures for recv and such, and await the recv in the add_sub/add_dealer/ect func?
This way any error downstream from recv will propagate back to the add_sub/add_-- func calls
Then, when we remove the pub, we cancel the handler. yea.

and we would like to know a way when we get a bad message on a particular URL/socket anyway. There should be some
logic s.t. if we get several 'bad' messages in a row, we blacklist him or something 
"""


class ExecutorMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        clsobj.log = get_logger(clsobj.__name__)

        if not hasattr(clsobj, 'registry'):
            clsobj.registry = {}

        if clsobj.__name__ != 'Executor':  # Exclude Executor base class
            clsobj.registry[clsobj.__name__] = clsobj

        return clsobj


class Executor(metaclass=ExecutorMeta):

    _recently_seen = CappedSet(max_size=Constants.Protocol.DupeTableSize)

    def __init__(self, loop, context, inproc_socket):
        self.loop = loop
        asyncio.set_event_loop(self.loop)
        self.context = context
        self.inproc_socket = inproc_socket

    async def recv_multipart(self, socket, callback_fn: types.MethodType, ignore_first_frame=False):
        self.log.warning("--- Starting recv on socket {} with callbackfn {} ---".format(socket, callback_fn))
        while True:
            self.log.debug("waiting for multipart msg...")
            msg = await socket.recv_multipart()

            self.log.debug("Got multipart msg: {}".format(msg))

            if ignore_first_frame:
                header = None
            else:
                assert len(msg) == 2, "Expected 2 frames (header, envelope) but got {}".format(msg)
                header = msg[0].decode()

            env_binary = msg[-1]
            env = self._validate_envelope(envelope_binary=env_binary, header=header)

            if not env:
                self.log.error("Could not validate envelope binary {}!".format(env_binary))
                continue

            Executor._recently_seen.add(env.meta.uuid)

            callback_fn(header=header, envelope=env)

    def call_on_mp(self, callback: str, header: str=None, envelope_binary: bytes=None, **kwargs):
        if header:
            kwargs['header'] = header

        cmd = ReactorCommand.create_callback(callback=callback, envelope_binary=envelope_binary, **kwargs)
        self.inproc_socket.send(cmd.serialize())

    def _validate_envelope(self, envelope_binary: bytes, header: str) -> Union[None, Envelope]:
        # TODO return/raise custom exceptions in this instead of just logging stuff and returning none

        # Deserialize envelope
        env = None
        try:
            env = Envelope.from_bytes(envelope_binary)
        except Exception as e:
            self.log.error("\n\n\nError deserializing envelope: {}\n\n\n".format(e))
            return None

        # Check seal
        if not env.verify_seal():
            self.log.error("\n\n\nSeal could not be verified for envelope {}\n\n\n".format(env))
            return None

        # If header is not none (meaning this is a ROUTE msg with an ID frame), then verify that the ID frame is
        # the same as the vk on the seal
        if header and (header != env.seal.verifying_key):
            self.log.error("\n\n\nHeader frame {} does not match seal's vk {}\nfor envelope {}\n\n\n"
                           .format(header, env.seal.verifying_key, env))
            return None

        # Make sure we haven't seen this message before
        if env.meta.uuid in Executor._recently_seen:
            self.log.warning("Duplicate envelope detect with UUID {}. Ignoring.".format(env.meta.uuid))
            return None

        # TODO -- checks timestamp to ensure this envelope is recv'd in a somewhat reasonable time (within N seconds)

        # If none of the above checks above return None, this envelope should be good
        return env

    def teardown(self):
        raise NotImplementedError


class SubPubExecutor(Executor):
    def __init__(self, loop, context, inproc_socket):
        super().__init__(loop, context, inproc_socket)
        self.sub = None
        self.sub_handlers = {}  # key is sub_url, value is asyncio Handler
        self.pubs = {}

    def _recv_pub_env(self, header: str, envelope: Envelope):
        self.log.debug("Recv'd pub envelope with header {} and env {}".format(header, envelope))
        self.call_on_mp(callback=ROUTE_CALLBACK, envelope_binary=envelope.serialize())

    # TODO -- is looping over all pubs ok?
    def send_pub(self, filter: str, envelope: bytes):
        assert isinstance(filter, str), "'id' arg must be a string"
        assert isinstance(envelope, bytes), "'envelope' arg must be bytes"
        assert len(self.pubs) > 0, "Attempted to publish data but publisher socket(s) is not configured"

        for url in self.pubs:
            self.log.debug("Publishing to... {} the envelope: {}".format(url, Envelope.from_bytes(envelope)))
            # self.log.info("Publishing to... {}".format(url))
            self.pubs[url].send_multipart([filter.encode(), envelope])

    def add_pub(self, url: str):
        if self.pubs.get(url):
            self.log.error("Attempted to add publisher on url {} but publisher socket already configured.".format(url))
            return

        self.log.info("Creating publisher socket on url {}".format(url))
        self.pubs[url] = self.context.socket(socket_type=zmq.PUB)
        self.pubs[url].bind(url)
        time.sleep(0.2)

    def add_sub(self, url: str, filter: str):
        assert isinstance(filter, str), "'id' arg must be a string"

        if not self.sub:
            self.log.info("Creating subscriber socket")
            self.sub = self.context.socket(socket_type=zmq.SUB)
            self.sub_handlers[url] = asyncio.ensure_future(self.recv_multipart(socket=self.sub,
                                                                               callback_fn=self._recv_pub_env,
                                                                               ignore_first_frame=True))

        self.log.info("Subscribing to url {} with filter '{}'".format(url, filter))
        self.sub.connect(url)
        self.sub.setsockopt(zmq.SUBSCRIBE, filter.encode())

    def remove_sub(self, url: str, filter: str):
        assert self.sub, "Remove sub command invoked but sub socket is not set"
        assert isinstance(filter, str), "'filter' arg must be a string"
        assert url in self.sub_handlers, "Attempted to remove a sub at url {} but no corresponding recv handler " \
                                         "was found in {}".format(url, self.sub_handlers)

        self.sub.setsockopt(zmq.UNSUBSCRIBE, filter.encode())
        self.sub.disconnect(url)

        self.sub_handlers[url].cancel()
        del(self.sub_handlers[url])

    def remove_pub(self, url: str):
        assert url in self.pubs, "Remove pub command invoked but pub socket is not set"
        self.pubs[url].disconnect(url)
        self.pubs[url].close()
        del self.pubs[url]

    def teardown(self):
        # TODO -- implement
        # cancel all futures, close all sockets
        pass


class DealerRouterExecutor(Executor):
    def __init__(self, loop, context, inproc_socket):
        super().__init__(loop, context, inproc_socket)

        # 'dealers' is a simple nested dict for holding sockets by URL as well as their associated recv handlers
        # key for 'dealers' is socket URL, and value is another dict with keys 'socket' (value is Socket instance)
        # and 'socket' (value is asyncio handler instance)
        self.dealers = defaultdict(dict)

        # Dict where key is reply UUID and value is the asyncio timeout handler
        self.expected_replies = {}

        self.router = None

    def _recv_request_env(self, header: str, envelope: Envelope):
        self.log.debug("Recv REQUEST envelope with header {} and envelope {}".format(header, envelope))
        self.call_on_mp(callback=ROUTE_REQ_CALLBACK, header=header, envelope_binary=envelope.serialize())

    def _recv_reply_env(self, header: str, envelope: Envelope):
        self.log.debug("Recv REPLY envelope with header {} and envelope {}".format(header, envelope))

        reply_uuid = envelope.meta.uuid
        if reply_uuid in self.expected_replies:
            self.log.debug("Removing reply with uuid {} from expected replies".format(reply_uuid))
            self.expected_replies[reply_uuid].cancel()
            del(self.expected_replies[reply_uuid])

        self.call_on_mp(callback=ROUTE_CALLBACK, header=header, envelope_binary=envelope.serialize())

    def _timeout(self, url: str, request_envelope: bytes, reply_uuid: int):
        assert reply_uuid in self.expected_replies, "Timeout triggered but reply_uuid was not in expected_replies"
        self.log.critical("Request to url {} timed out! (reply uuid {} not found). Request envelope: {}"
                          .format(url, reply_uuid, request_envelope))

        del(self.expected_replies[reply_uuid])
        self.call_on_mp(callback=ROUTE_TIMEOUT_CALLBACK, envelope_binary=request_envelope)


    def add_router(self, url: str):
        assert self.router is None, "Attempted to add router on url {} but socket already configured".format(url)

        self.log.info("Creating router socket on url {}".format(url))
        self.router = self.context.socket(socket_type=zmq.ROUTER)
        self.router.bind(url)
        asyncio.ensure_future(self.recv_multipart(socket=self.router, callback_fn=self._recv_request_env))

    def add_dealer(self, url: str, id: str):
        assert url not in self.dealers, "Url {} already in self.dealers {}".format(url, self.dealers)
        self.log.info("Creating dealer socket for url {} with id {}".format(url, id))
        assert isinstance(id, str), "'id' arg must be a string"

        socket = self.context.socket(socket_type=zmq.DEALER)
        socket.identity = id.encode('ascii')

        self.log.info("Dealer socket connecting to url {}".format(url))
        socket.connect(url)

        future = asyncio.ensure_future(self.recv_multipart(socket=socket,
                                                           callback_fn=self._recv_reply_env, ignore_first_frame=True))

        self.dealers[url][_SOCKET] = socket
        self.dealers[url][_HANDLER] = future

    # TODO pass in the intended replier's vk so we can be sure the reply we get is actually from him
    def request(self, url: str, reply_uuid: str, envelope: bytes, timeout=0):
        self.log.critical("ay we requesting /w reply uuid {} and env {}".format(reply_uuid, envelope))
        assert url in self.dealers, "Attempted to make request to url {} that is not in self.dealers {}"\
            .format(url, self.dealers)
        assert isinstance(envelope, bytes), "'envelope' arg must be bytes"

        reply_uuid = int(reply_uuid)
        timeout = int(timeout)

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

    def remove_router(self, url):
        assert self.router, "Tried to remove router but self.router is not set"
        self.log.critical("remove router not implemented")
        raise NotImplementedError
        # self.log.info("Removing router at url {}".format(url))

    def remove_dealer(self, url, id=''):
        assert url in self.dealers, "Attempted to remove dealer url {} that is not in list of dealers {}"\
            .format(url, self.dealers)

        self.log.info("Removing dealer at url {} with id {}".format(url, id))

        socket = self.dealers[url][_SOCKET]
        future = self.dealers[url][_HANDLER]

        # Clean up socket and cancel future
        socket.disconnect(url)
        socket.close()
        future.cancel()

        # 'destroy' references to socket/future (not sure if this is necessary tbh)
        self.dealers[url][_SOCKET] = None
        self.dealers[url][_HANDLER] = None
        del(self.dealers[url])

    def teardown(self):
        # TODO -- implement
        # cancel all futures, close all sockets
        pass



