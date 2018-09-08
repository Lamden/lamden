from cilantro.messages.base.base import MessageBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.protocol.structures import EnvelopeAuth
from cilantro.logger.base import get_logger
import zmq.asyncio, asyncio

from collections import defaultdict, deque
from functools import wraps
from typing import List


def vk_lookup(func):
    @wraps(func)
    def _func(self, *args, **kwargs):
        contains_vk = 'vk' in kwargs and kwargs['vk']
        contains_ip = 'ip' in kwargs and kwargs['ip']

        if contains_vk and not contains_ip:
            if not self.manager.pending_commands:
                self.log.debugv("Cannot execute vk lookup yet as event loop is not running, or overlay is not ready."
                                " Adding func {} to command queue".format(func.__name__))
                self.manager.pending_commands.append((self, func.__name__, args, kwargs))
                return

            cmd_id = self.manager.overlay_cli.get_node_from_vk(kwargs['vk'])
            assert cmd_id not in self.pending_lookups, "Collision! Uuid {} already in pending lookups {}".format(cmd_id, self.pending_lookups)
            self.log.debugv("Looking up vk {}, which returned command id {}".format(kwargs['vk'], cmd_id))

            self.pending_lookups[cmd_id] = (func.__name__, args, kwargs)
            self.manager.pending_commands[cmd_id] = self

        # If the 'ip' key is already set in kwargs, no need to do a lookup
        else:
            func(self, *args, **kwargs)

    return _func


class LSocket:

    def __init__(self, socket: zmq.asyncio.Socket, manager, name='LSocket'):
        self.socket = socket
        self.manager = manager
        self.log = get_logger(name)

        self.pending_commands = deque()  # A list of defered commands that are flushed once this socket connects/binds
        self.pending_lookups = {}  # A dict of event_id to tuple, where the tuple again represents a command execution

    def handle_overlay_event(self, event: dict):
        assert event['event_id'] in self.pending_lookups, "Socket got overlay event {} not in pending lookups {}"\
                                                           .format(event, self.pending_lookups)
        assert event['event'] == 'got_ip', "Socket only knows how to handle got_ip events, but got {}".format(event)

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

            # TODO do we need to defer execution of this while loop until all lookups are resolved? I kinda feel like we do...
            while True:
                try:
                    msg = await socket.recv_multipart()
                except Exception as e:
                    if type(e) is asyncio.CancelledError:
                        self.log.important("Socket got asyncio.CancelledError. Breaking from lister loop.")  # TODO change log level on this
                        break
                    else:
                        self.log.critical("Socket got exception! Exception:\n{}".format(e))
                        raise e

                self.log.spam("Socket recv multipart msg:\n{}".format(msg))
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
        if should_connect:
            self.socket.connect(url)
        else:
            self.socket.bind(url)

        if len(self.pending_lookups) == 0:
            self._flush_pending_commands()

    def _flush_pending_commands(self):
        if not len(self.pending_commands):  # Return if there are no commands to flush
            return

        assert asyncio.get_event_loop().is_running(), "Event loop must be running to flush commands"
        assert self.manager.overlay_ready, "Overlay must be ready to flush commands"
        assert len(self.pending_lookups) == 0, 'All lookups must be resolved before we can flush pending commands'

        self.log.debugv("Composer flushing {} commands from queue".format(len(self.pending_commands)))

        for cmd_name, args, kwargs in self.pending_commands:
            self.log.spam("Executing pending command {} with args {} and kwargs {}".format(cmd_name, args, kwargs))
            getattr(self, cmd_name)(*args, **kwargs)

    def _defer_func(self, cmd_name):
        def _capture_args(*args, **kwargs):
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
        if len(self.pending_lookups) > 0 or not self.manager.overlay_ready:
            self.log.debugv("Socket is not ready yet. Defering method named {}".format(item))
            self.log.important2("Socket is not ready yet. Defering method named {}".format(item))
            return self._defer_func(item)
        else:
            return underlying

