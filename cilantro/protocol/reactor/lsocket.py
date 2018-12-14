from cilantro.messages.base.base import MessageBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.protocol.structures.envelope_auth import EnvelopeAuth
from cilantro.protocol.overlay.auth import Auth
from cilantro.logger.base import get_logger
import zmq.asyncio, asyncio, os

from collections import defaultdict, deque
from functools import wraps
from typing import List, Union
from os.path import join


RDY_WAIT_INTERVAL = 2.0  # TODO move this to constants, and explain it
MAX_RDY_WAIT = 20.0  # TODO move this to constants, and explain it


def vk_lookup(func):
    @wraps(func)
    def _func(self, *args, **kwargs):
        contains_vk = 'vk' in kwargs and kwargs['vk']
        contains_ip = 'ip' in kwargs and kwargs['ip']

        if contains_vk and not contains_ip:
            cmd_id = self.manager.overlay_client.get_node_from_vk(kwargs['vk'], domain=self.domain, secure=self.secure)
            assert cmd_id not in self.pending_lookups, "Collision! Uuid {} already in pending lookups {}".format(cmd_id, self.pending_lookups)

            self.log.socket("Looking up vk {}".format(kwargs['vk']))  # TODO remove
            self.pending_lookups[cmd_id] = (func.__name__, args, kwargs)
            self.ready = False
            self._start_wait_rdy()
            self.manager.pending_lookups[cmd_id] = self

        # If the 'ip' key is already set in kwargs, no need to do a lookup
        else:
            func(self, *args, **kwargs)

    return _func


class LSocket:

    DEFERED_FUNCS = ('send_multipart', 'send')

    def __init__(self, socket: zmq.asyncio.Socket, manager, name='LSocket', secure=False, domain='*'):
        self.log = get_logger(name)
        self.name = name
        self.secure = secure
        self.socket = socket
        self.domain = domain

        if secure:
            self.socket = Auth.secure_socket(
                self.socket,
                manager.secret,
                manager.public_key,
                self.domain
            )

        self.manager = manager

        self.pending_commands = deque()  # A list of defered commands that are flushed once this socket connects/binds
        self.pending_lookups = {}  # A dict of event_id to tuple, where the tuple again represents a command execution
        self.ready = False  # Gets set to True when all pending_lookups have been resolved, and we BIND/CONNECT

        self.handler_added = False
        self.check_rdy_fut = None

    def handle_overlay_event(self, event: dict):
        assert event['event_id'] in self.pending_lookups, "Socket got overlay event {} not in pending lookups {}"\
                                                           .format(event, self.pending_lookups)
        self.log.debugv("Socket handling overlay event {}".format(event))

        cmd_name, args, kwargs = self.pending_lookups.pop(event['event_id'])
        if 'ip' in event:
            kwargs['ip'] = event['ip']
        getattr(self, cmd_name)(*args, **kwargs)

    def add_handler(self, handler_func, handler_key=None, start_listening=False) -> Union[asyncio.Future, asyncio.coroutine]:
        async def _listen(socket, func, key):
            self.log.debug("Starting listener handler key {}".format(key))

            # TODO
            # I dont think we need this. We cant recv ASAP, and conn/bind as needed. Only thing we need to defer are
            # sends --davis
            # self.log.debugv("Listener waiting for socket to finish all lookups")
            # self._start_wait_rdy()
            # await self.check_rdy_fut
            # self.log.debugv("Listener done waiting for socket to finish lookups")

            while True:
                try:
                    self.log.spam("Socket waiting for multipart msg...")
                    msg = await socket.recv_multipart()
                except asyncio.CancelledError:
                    self.log.warning("Socket got asyncio.CancelledError. Breaking from lister loop.")
                    break

                self.log.spam("Socket recv multipart msg:\n{}".format(msg))

                if key is not None:
                    func(msg, key)
                else:
                    func(msg)

        assert not self.handler_added, "Handler already added for socket named {}".format(self.name)

        self.log.debug("Socket adding handler func named {} with handler key {}".format(handler_func, handler_key))
        self.handler_added = True
        coro = _listen(self.socket, handler_func, handler_key)

        if start_listening:
            return asyncio.ensure_future(coro)
        else:
            return coro

    def send_msg(self, msg: MessageBase, header: bytes=None):
        """
        Convenience method to send a message over this socket using send_multipart. If 'header' arg exists, it will be
        used as the first frame of the message. For example, should be a filter if sending over PUB, or an ID frame if
        it is a Router socket.
        :param msg: The MessageBase instance to wrap in an envelope and send
        :param header: The header frame to use. If None, no header frame will be sent.
        """
        self.send_envelope(env=self._package_msg(msg), header=header)

    def send_envelope(self, env: Envelope, header: bytes=None):
        """
        Same as send_msg, but for an Envelope instance. See documentation for send_msg.
        """
        data = env.serialize()

        if header:
            assert type(header) is bytes, "Header arg must be bytes, not {}".format(type(header))
            self.send_multipart([header, data])
        else:
            self.send_multipart([data])

    @vk_lookup
    def connect(self, port: int, protocol: str='tcp', ip: str='', vk: str=''):
            self._connect_or_bind(should_connect=True, port=port, protocol=protocol, ip=ip, vk=vk)

    @vk_lookup
    def bind(self, port: int, protocol: str='tcp', ip: str='', vk: str=''):
        self._connect_or_bind(should_connect=False, port=port, protocol=protocol, ip=ip, vk=vk)

    def _connect_or_bind(self, should_connect: bool, port: int, protocol: str='tcp', ip: str='', vk: str=''):
        assert ip, "Expected ip arg to be present!"
        assert protocol in ('tcp', 'ipc'), "Only tcp/ipc protocol is supported, not {}".format(protocol)
        # TODO validate other args (port is an int within some range, ip address is a valid, ect)

        if ip == os.getenv('HOST_IP'): ip = '0.0.0.0'
        url = "{}://{}:{}".format(protocol, ip, port)
        self.log.socket("{} to URL {}".format('CONNECTING' if should_connect else 'BINDING', url))

        if should_connect:
            if self.secure:
                self.socket.curve_serverkey = Auth.vk2pk(vk)
                Auth.configure_auth(self.manager.auth, self.domain)
            self.socket.connect(url)
        else:
            if self.secure:
                self.socket.curve_server = True
                Auth.configure_auth(self.manager.auth, self.domain)
            self.socket.bind(url)

        if len(self.pending_lookups) == 0:
            self.log.debugv("Pending lookups empty. Flushing commands")
            self.ready = True
            self._flush_pending_commands()
        else:
            self.log.debugv("Not flushing commands yet, pending lookups not empty: {}".format(self.pending_lookups))

    def _flush_pending_commands(self):
        assert len(self.pending_lookups) == 0, 'All lookups must be resolved before we can flush pending commands'
        assert self.ready, "Socket must be ready to flush pending commands!"
        self.log.debugv("Flushing {} commands from queue".format(len(self.pending_commands)))

        for cmd_name, args, kwargs in self.pending_commands:
            self.log.spam("Executing pending command named '{}' with args {} and kwargs {}".format(cmd_name, args, kwargs))
            getattr(self, cmd_name)(*args, **kwargs)

    def _defer_func(self, cmd_name):
        def _capture_args(*args, **kwargs):
            self.log.spam("Socket defered func named {} with args {} and kwargs {}".format(cmd_name, args, kwargs))
            self.pending_commands.append((cmd_name, args, kwargs))
        return _capture_args

    # TODO move this to its own module? Kind of annoying to have to pass in signing_key and verifying_key tho....
    def _package_msg(self, msg: MessageBase) -> Envelope:
        """
        Convenience method to package a message into an envelope
        :param msg: The MessageBase instance to package
        :return: An Envelope instance
        """
        assert type(msg) is not Envelope, "Attempted to package a 'message' that is already an envelope"
        assert issubclass(type(msg), MessageBase), "Attempted to package a message that is not a MessageBase subclass"

        return Envelope.create_from_message(message=msg, signing_key=self.manager.signing_key,
                                            verifying_key=self.manager.verifying_key)

    # TODO move this to its own module? Kind of annoying to have to pass in signing_key and verifying_key tho....
    def _package_reply(self, reply: MessageBase, req_env: Envelope) -> Envelope:
        """
        Convenience method to create a reply envelope. The difference between this func and _package_msg, is that
        in the reply envelope the UUID must be the hash of the original request's uuid (not some randomly generated int)
        :param reply: The reply message (an instance of MessageBase)
        :param req_env: The original request envelope (an instance of Envelope)
        :return: An Envelope instance
        """
        self.log.spam("Creating REPLY envelope with msg type {} for request envelope {}".format(type(reply), req_env))
        request_uuid = req_env.meta.uuid
        reply_uuid = EnvelopeAuth.reply_uuid(request_uuid)

        return Envelope.create_from_message(message=reply, signing_key=self.manager.signing_key,
                                            verifying_key=self.manager.verifying_key, uuid=reply_uuid)

    async def _wait_socket_rdy(self):
        self.log.debug("Polling until socket ready...")
        duration_waited = 0

        while not self.ready:
            if duration_waited > MAX_RDY_WAIT:
                if len(self.pending_lookups) > 0:
                    # TODO trigger callback on Worker class for URL could not be reached or something
                    msg = "Socket failed to bind/connect to url(s) in {} seconds! Abandoning pending lookups: {}" \
                          .format(MAX_RDY_WAIT, self.pending_lookups)
                    self.log.error(msg)
                else:
                    self.log.debugv("No connect/bind calls to socket in {} seconds. Setting socket to ready.")

                break  # Break out of loop if we timeout

            self.log.spam("Socket not ready yet...waiting {} seconds".format(RDY_WAIT_INTERVAL))
            await asyncio.sleep(RDY_WAIT_INTERVAL)
            duration_waited += RDY_WAIT_INTERVAL

        self.pending_lookups.clear()
        self.ready = True
        self._flush_pending_commands()
        self.check_rdy_fut = None

    def __getattr__(self, item):
        assert hasattr(self.socket, item), "Underlying socket object {} has no attribute named {}".format(self.socket, item)
        underlying = getattr(self.socket, item)

        # If we are accessing an attribute that does not exist in LSocket, we assume its a attribute on self.socket
        if not callable(underlying):
            return underlying

        # Otherwise, we assume its a method on self.socket

        # If this socket is not ready (ie it has not bound/connected yet), defer execution of this method
        if not self.ready and item in self.DEFERED_FUNCS:
            self.log.debugv("Socket is not ready yet. Deferring method named {}".format(item))
            self._start_wait_rdy()
            return self._defer_func(item)
        else:
            self.log.important("returning underlying atr {} for item {}".format(item, underlying))  # TODO remove
            return underlying

    def _start_wait_rdy(self):
        if not self.check_rdy_fut:
            self.log.debug("Starting future to check for socket ready")
            self.check_rdy_fut = asyncio.ensure_future(self._wait_socket_rdy())
