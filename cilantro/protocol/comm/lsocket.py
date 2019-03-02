from cilantro.messages.base.base import MessageBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.protocol.structures.envelope_auth import EnvelopeAuth
from cilantro.protocol.utils.socket import SocketUtil
from cilantro.logger.base import get_logger
import zmq.asyncio, asyncio, os

from collections import defaultdict, deque
from functools import wraps
from typing import List, Union
from os.path import join


def vk_lookup(func):
    @wraps(func)
    def _func(self, *args, **kwargs):
        contains_vk = 'vk' in kwargs and kwargs['vk']
        contains_ip = 'ip' in kwargs and kwargs['ip']

        if contains_vk and not contains_ip:
            cmd_id = self.manager.overlay_client.get_node_from_vk(kwargs['vk'], domain=self.domain, secure=self.secure)
            assert cmd_id not in self.pending_lookups, "Collision! Uuid {} already in pending lookups {}".format(cmd_id, self.pending_lookups)

            self.log.socket("{} call resolving ip for vk {}".format(func.__name__, kwargs['vk']))
            cmd_tuple = (func.__name__, args, kwargs)

            self.pending_lookups[cmd_id] = cmd_tuple
            self.manager.pending_lookups[cmd_id] = self
            self.conn_tracker[kwargs['vk']] = cmd_tuple

            # DEBUG -- TODO DELETE
            # self.log.important3("Adding vk {} to conn tracker with cmd tuple {}".format(kwargs['vk'], cmd_tuple))
            # END DEBUG

        # If the 'ip' key is already set in kwargs, no need to do a lookup
        else:
            func(self, *args, **kwargs)

    return _func


class LSocketBase:
    # TODO
    # do we even need the defer mechanism? Currently, no other sockets use this besides Router, which implements
    # is specially. I guess it could be useful for DEALER or PUSH/PULL sockets (if we ever use them)? --davis
    DEFERRED_FUNCS = ('send_multipart', 'send')

    def __init__(self, socket: zmq.asyncio.Socket, manager, name='', secure=False, domain='*'):
        name = name or type(self).__name__
        self.log, self.name = get_logger(name), name
        self.secure, self.socket, self.domain, self.manager = secure, socket, domain, manager

        if secure:
            self.socket = SocketUtil.secure_socket(
                self.socket,
                manager.secret,
                manager.public_key,
                self.domain
            )

        # NOTE: A command execution is represented by a tuple of form (func_name: str, args: list, kwargs: dict)
        self.pending_commands = deque()  # A list of defered commands that are flushed once this socket is ready
        self.pending_lookups = {}  # A dict of event_id to tuple, where the tuple again represents a command execution
        self.conn_tracker = {}  # A dict of vk (as str) to bind/conn command executions. Used for auto reconnects
        self.active_conns = set()  # A set of URLs we are connected/bound to

        self.ready = True  # If False, all DEFERRED_FUNCS will be suspended until ready. Used by subclasses
        self.handler_added = False  # We use this just for dev sanity checks, to ensure only one handler is added

    @vk_lookup
    def connect(self, port: int, protocol: str='tcp', ip: str='', vk: str=''):
        self._connect_or_bind(should_connect=True, port=port, protocol=protocol, ip=ip, vk=vk)

    @vk_lookup
    def bind(self, port: int, protocol: str='tcp', ip: str='', vk: str=''):
        self._connect_or_bind(should_connect=False, port=port, protocol=protocol, ip=ip, vk=vk)

    def send_msg(self, msg: MessageBase, header: bytes=None):
        """ Convenience method to send a message over this socket using send_multipart. If 'header' arg exists, it will be
        used as the first frame of the message. For example, should be a filter if sending over PUB, or an ID frame if
        it is a Router socket.
        :param msg: The MessageBase instance to wrap in an envelope and send
        :param header: The header frame to use. If None, no header frame will be sent. """
        self.send_envelope(env=self._package_msg(msg), header=header)

    def send_envelope(self, env: Envelope, header: bytes=None):
        """ Same as send_msg, but for an Envelope instance. See documentation for send_msg. """
        data = env.serialize()

        if header is not None:
            assert type(header) is bytes, "Header arg must be bytes, not {}".format(type(header))
            self.send_multipart([header, data])
        else:
            self.send_multipart([data])

    def add_handler(self, handler_func, handler_key=None, start_listening=False) -> Union[asyncio.Future, asyncio.coroutine]:
        """ Registered a handler function for data received on this socket.
        :param handler_func: The handler function, which is invoked with the raw frames received over the wire (as a
        list), and optionally the handler_key if this arg is specified
        :param handler_key: A 'key' for differentiating which socket triggers this handler. This is useful when you
        have multiple sockets but you wish to reuse the same handler func.
        :param start_listening: If True, the socket listener coroutine is automatically started, and a Future is
        returned. Otherwise, the listener coro itself is returned and must be started manually.
        :return: A coroutine if start_listening is False, otherwise a Future. """
        assert not self.handler_added, "Handler already added for socket named {}".format(self.name)

        self.log.spam("Socket adding handler func named {} with handler key {}".format(handler_func, handler_key))
        self.handler_added = True
        coro = self._listen(handler_func, handler_key)

        if start_listening:
            return asyncio.ensure_future(coro)
        else:
            return coro

    async def _listen(self, func, key):
        self.log.debug("Starting listener handler key {}".format(key))

        while True:
            try:
                self.log.spam("Socket waiting for multipart msg...")
                msg = await self.socket.recv_multipart()
                self.log.spam("Socket received multipart msg: {}".format(msg))
                should_forward = self._process_msg(msg)
            except Exception as e:
                if type(e) is asyncio.CancelledError:
                    self.log.warning("Socket got asyncio.CancelledError. Breaking from lister loop.")
                    return
                else:
                    self.log.fatal("OHhhh nooooooo we got a ZMQ exception! Error: {}".format(e))

            if not should_forward:
                continue

            if key is not None:
                func(msg, key)
            else:
                func(msg)

    def _process_msg(self, msg: List[bytes]) -> bool:
        """ Custom messages processing to be implemented by subclasses. This method should return True if the
        msg should be forwarded to the user handlers, and False otherwise. See LSocketRouter for example."""
        return True

    def handle_overlay_event(self, event: dict):
        self.log.spam("Socket handling overlay event {}".format(event))
        ev_name = event['event']

        if ev_name == 'got_ip':
            self._handle_got_ip(event)
        elif ev_name == 'not_found':
            self._handle_not_found(event)
        elif ev_name == 'node_online':
            self._handle_node_online(event)
        else:
            raise Exception("LSocket got overlay event '{}' that it is not configured to handle!".format(ev_name))

    def _handle_got_ip(self, event: dict):
        assert event['event_id'] in self.pending_lookups, "LSocket got 'got_ip' event that is not in pending lookups"

        cmd_name, args, kwargs = self.pending_lookups.pop(event['event_id'])
        kwargs['ip'] = event['ip']
        getattr(self, cmd_name)(*args, **kwargs)

    def _handle_not_found(self, event: dict):
        assert event['event_id'] in self.pending_lookups, "LSocket got 'not_found' event that is not in pending lookups"
        self.log.socket("Could not resolve IP for VK {}".format(event['vk']))
        del self.pending_lookups[event['event_id']]

    def _handle_node_online(self, event: dict):
        if event['vk'] not in self.conn_tracker:
            self.log.debugv("Socket never connected to node with vk {}. Ignoring node_online event.".format(event['vk']))
            return

        cmd_name, args, kwargs = self.conn_tracker[event['vk']]
        kwargs['ip'] = event['ip']
        url = self._get_url_from_kwargs(**kwargs)

        self.log.info("Node with vk {} and ip {} has come back online. Re-establishing connection for URL {}"
                      .format(event['vk'], event['ip'], url))

        # First disconnect if we are already connected to this peer
        if url in self.active_conns:
            self.log.debugv("First disconnecting from URL {} before reconnecting".format(url))
            self.socket.disconnect(url)

        # TODO remove this else
        else:
            self.log.important("URL {} not in self.active_conns {}".format(url, self.active_conns))

        # We wrap the reconnect in the try/except to ignore 'address already in use' errors from attempting to bind
        # to an address that we already bound to. I know this is mad hacky but its 'works' until we come up
        # with something more clever --davis
        try:
            getattr(self, cmd_name)(*args, **kwargs)
        except zmq.error.ZMQError as e:
            if str(e) != 'Address already in use':
                self.log.warning("Got error trying to reconnect that is not 'Address in use'!!! Error: {}".format(e))

    def _connect_or_bind(self, should_connect: bool, port: int, protocol: str='tcp', ip: str='', vk: str=''):
        assert ip, "Expected ip arg to be present!"
        assert protocol in ('tcp', 'ipc'), "Only tcp/ipc protocol is supported, not {}".format(protocol)
        # TODO validate other args (port is an int within some range, ip address is a valid, ect)

        if ip == os.getenv('HOST_IP'): ip = '0.0.0.0'
        url = self._get_url_from_kwargs(port=port, protocol=protocol, ip=ip)
        self.active_conns.add(url)
        self.log.socket("{} to URL {}".format('CONNECTING' if should_connect else 'BINDING', url))

        if should_connect:
            if self.secure:
                self.socket.curve_serverkey = Keys.vk2pk(vk)
                self.manager.configure_auth(self.domain)
            self.socket.connect(url)
        else:
            if self.secure:
                self.socket.curve_server = True
                self.manager.configure_auth(self.domain)
            self.socket.bind(url)

    def __getattr__(self, item):
        assert hasattr(self.socket, item), "Underlying socket object {} has no attribute named {}".format(self.socket, item)
        underlying = getattr(self.socket, item)

        # If we are accessing an attribute that does not exist in LSocket, we assume its a attribute on self.socket
        if not callable(underlying):
            return underlying

        # Otherwise, we assume its a method on self.socket

        # If this socket is not ready defer execution of this method
        if not self.ready and item in self.DEFERRED_FUNCS:
            self.log.debugv("Socket is not ready yet. Deferring method named {}".format(item))
            return self._defer_func(item)
        else:
            return underlying

    def _get_url_from_kwargs(self, **kwargs):
        port, protocol, ip = kwargs.get('port'), kwargs.get('protocol', 'tcp'), kwargs.get('ip'),
        assert port, "port missing from kwargs {}".format(kwargs)
        assert protocol, "protocol missing from kwargs {}".format(kwargs)
        assert ip, "ip missing from kwargs {}".format(kwargs)
        return "{}://{}:{}".format(protocol, ip, port)

    def _defer_func(self, cmd_name):
        def _capture_args(*args, **kwargs):
            self.log.spam("Socket defered func named {} with args {} and kwargs {}".format(cmd_name, args, kwargs))
            self.pending_commands.append((cmd_name, args, kwargs))

        return _capture_args

    def _package_msg(self, msg: MessageBase) -> Envelope:
        """ Convenience method to package a message into an envelope
        :param msg: The MessageBase instance to package
        :return: An Envelope instance
        """
        assert type(msg) is not Envelope, "Attempted to package a 'message' that is already an envelope"
        assert issubclass(type(msg), MessageBase), "Attempted to package a message that is not a MessageBase subclass"

        return Envelope.create_from_message(message=msg, signing_key=self.manager.signing_key,
                                            verifying_key=self.manager.verifying_key)

    def _package_reply(self, reply: MessageBase, req_env: Envelope) -> Envelope:
        """ Convenience method to create a reply envelope. The difference between this func and _package_msg, is that
        in the reply envelope the UUID must be the hash of the original request's uuid (not some randomly generated int)
        :param reply: The reply message (an instance of MessageBase)
        :param req_env: The original request envelope (an instance of Envelope)
        :return: An Envelope instance """
        self.log.spam("Creating REPLY envelope with msg type {} for request envelope {}".format(type(reply), req_env))
        request_uuid = req_env.meta.uuid
        reply_uuid = EnvelopeAuth.reply_uuid(request_uuid)

        return Envelope.create_from_message(message=reply, signing_key=self.manager.signing_key,
                                            verifying_key=self.manager.verifying_key, uuid=reply_uuid)

    def _flush_pending_commands(self):
        self.log.debug("Flushing {} pending commands from queue".format(len(self.pending_commands)))
        for cmd_name, args, kwargs in self.pending_commands:
            self.log.spam("Executing pending command named '{}' with args {} and kwargs {}".format(cmd_name, args, kwargs))
            getattr(self, cmd_name)(*args, **kwargs)
        self.pending_commands.clear()
