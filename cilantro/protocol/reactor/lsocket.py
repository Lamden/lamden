from cilantro.messages.base.base import MessageBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.protocol.structures import EnvelopeAuth
from cilantro.protocol.overlay.ironhouse import Ironhouse
from cilantro.logger.base import get_logger
import zmq.asyncio, asyncio, os

from collections import defaultdict, deque
from functools import wraps
from typing import List
from os.path import join


RDY_WAIT_INTERVAL = 0.2  # TODO move this to constants, and explain it
MAX_RDY_WAIT = 10.0  # TODO move this to constants, and explain it


def vk_lookup(func):
    @wraps(func)
    def _func(self, *args, **kwargs):
        contains_vk = 'vk' in kwargs and kwargs['vk']
        contains_ip = 'ip' in kwargs and kwargs['ip']

        if contains_vk and not contains_ip:
            cmd_id = self.manager.overlay_client.get_node_from_vk(kwargs['vk'], domain=self.domain)
            assert cmd_id not in self.pending_lookups, "Collision! Uuid {} already in pending lookups {}".format(cmd_id, self.pending_lookups)

            self.log.debugv("Looking up vk {}, which returned command id {}".format(kwargs['vk'], cmd_id))
            self.pending_lookups[cmd_id] = (func.__name__, args, kwargs)
            self.manager.pending_lookups[cmd_id] = self
            self.manager.auth.configure_curve(domain=self.domain, location=self.location)

        # If the 'ip' key is already set in kwargs, no need to do a lookup
        else:
            func(self, *args, **kwargs)

    return _func


class LSocket:

    def __init__(self, socket: zmq.asyncio.Socket, manager, name='LSocket', secure=False, domain='*'):
        self.log = get_logger(name)
        self.secure = secure
        self.socket = socket
        self.domain = domain
        self.location = join(Ironhouse.base_dir, self.domain) if self.domain != '*' else Ironhouse.authorized_keys_dir
        if secure:
            self.socket = Ironhouse.secure_socket(self.socket, manager.secret, manager.public_key)
            self.socket.curve_secretkey = manager.secret
            self.socket.curve_publickey = manager.public_key
            if self.domain != '*':
                os.makedirs(self.location, exist_ok=True)
                self.socket.zap_domain = self.domain.encode()

        self.manager = manager


        self.pending_commands = deque()  # A list of defered commands that are flushed once this socket connects/binds
        self.pending_lookups = {}  # A dict of event_id to tuple, where the tuple again represents a command execution
        self.ready = False  # Gets set to True when all pending_lookups have been resolved, and we BIND/CONNECT

    def handle_overlay_event(self, event: dict):
        assert event['event_id'] in self.pending_lookups, "Socket got overlay event {} not in pending lookups {}"\
                                                           .format(event, self.pending_lookups)
        assert event['event'] == 'got_ip', "Socket only knows how to handle got_ip events, but got {}".format(event)
        assert 'ip' in event, "got_ip event {} expected to have key 'ip'".format(event)
        self.log.debug("Socket handling overlay event {}".format(event))

        cmd_name, args, kwargs = self.pending_lookups.pop(event['event_id'])
        kwargs['ip'] = event['ip']
        getattr(self, cmd_name)(*args, **kwargs)

    def flush_lookup_commands(self):
        self.log.debug("Flushing lookup commands:\n{}".format(self.pending_lookups))

        for cmd_name, args, kwargs in self.pending_commands:
            self.log.spam("Executing pending command {} with args {} and kwargs {}".format(cmd_name, args, kwargs))
            getattr(self, cmd_name)(*args, **kwargs)

    def add_handler(self, handler_func, msg_types: List[MessageBase]=None, start_listening=False) -> asyncio.Future or asyncio.coroutine:
        async def _listen(socket, handler_func):
            self.log.socket("Starting listener on socket {}".format(socket))
            duration_waited = 0

            while True:
                if duration_waited > MAX_RDY_WAIT and not self.ready:
                    raise Exception("Socket failed to bind/connect in {} seconds!")

                if not self.ready:
                    self.log.spam("Socket not ready yet...waiting {} seconds".format(RDY_WAIT_INTERVAL))  # TODO remove this? it be hella noisy..
                    await asyncio.sleep(RDY_WAIT_INTERVAL)
                    duration_waited += RDY_WAIT_INTERVAL
                    continue

                try:
                    self.log.spam("Socket waiting for multipart msg...")
                    msg = await socket.recv_multipart()
                    self.log.spam("Socket recv multipart msg:\n{}".format(msg))
                except asyncio.CancelledError:
                    self.log.warning("Socket got asyncio.CancelledError. Breaking from lister loop.")
                    break

                handler_func(msg)

        if start_listening:
            return asyncio.ensure_future(_listen(self.socket, handler_func))
        else:
            return _listen(self.socket, handler_func)

    @vk_lookup
    def connect(self, port: int, protocol: str='tcp', ip: str='', vk: str=''):
        self._connect_or_bind(should_connect=True, port=port, protocol=protocol, ip=ip, vk=vk)

    @vk_lookup
    def bind(self, port: int, protocol: str='tcp', ip: str='', vk: str=''):
        self._connect_or_bind(should_connect=False, port=port, protocol=protocol, ip=ip, vk=vk)

    def _connect_or_bind(self, should_connect: bool, port: int, protocol: str='tcp', ip: str='', vk: str=''):
        assert ip, "Expected ip arg to be present!"
        assert protocol in ('tcp', 'icp'), "Only tcp/ipc protocol is supported, not {}".format(protocol)
        # TODO validate other args (port is an int within some range, ip address is a valid, ect)

        url = "{}://{}:{}".format(protocol, ip, port)
        self.log.socket("{} to URL {}".format('CONNECTING' if should_connect else 'BINDING', url))
        if should_connect:
            if self.secure:
                self.socket.curve_serverkey = Ironhouse.vk2pk(vk)
                self.manager.auth.configure_curve(domain=self.domain, location=self.location)
            self.socket.connect(url)
        else:
            if self.secure:
                self.socket.curve_server = True
                self.manager.auth.configure_curve(domain=self.domain, location=self.location)
            self.socket.bind(url)

        self.log.critical('!!!')

        if len(self.pending_lookups) == 0:
            self.log.debugv("Pending lookups empty. Flushing commands")
            self.ready = True
            self._flush_pending_commands()
        else:
            self.log.debugv("Not flushing commands yet, pending lookups not empty: {}".format(self.pending_lookups))

    def _flush_pending_commands(self):
        assert len(self.pending_lookups) == 0, 'All lookups must be resolved before we can flush pending commands'
        assert self.ready, "Socket must be ready to flush pending commands!"
        self.log.debugv("Composer flushing {} commands from queue".format(len(self.pending_commands)))

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

        return Envelope.create_from_message(message=msg, signing_key=self.signing_key, verifying_key=self.verifying_key)

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

        return Envelope.create_from_message(message=reply, signing_key=self.signing_key,
                                            verifying_key=self.verifying_key, uuid=reply_uuid)

    def __getattr__(self, item):
        self.log.spam("called __getattr__ with item {}".format(item))  # TODO remove this
        assert hasattr(self.socket, item), "Underlying socket object {} has no attribute named {}".format(self.socket, item)
        underlying = getattr(self.socket, item)

        # If we are accessing an attribute that does not exist in LSocket, we assume its a attribute on self.socket
        # Otherwise, we assume its a method on self.socket
        if not callable(underlying):
            self.log.important2("{} is not callable, returning it as presumably an attribute".format(underlying))  # TODO remmove
            return underlying

        # If this socket is not ready (ie it has not bound/connected yet), defer execution of this method
        if not self.ready:
            self.log.debugv("Socket is not ready yet. Defering method named {}".format(item))
            return self._defer_func(item)
        else:
            return underlying
