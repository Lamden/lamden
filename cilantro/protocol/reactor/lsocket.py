from cilantro.protocol.reactor.socket_manager import SocketManager
from cilantro.messages.base.base import MessageBase
from cilantro.logger.base import get_logger
import zmq.asyncio, asyncio

from functools import wraps
from typing import List


def vk_lookup(func):
    @wraps(func)
    def _func(self, *args, **kwargs):
        contains_vk = 'vk' in kwargs and kwargs['vk']
        contains_ip = 'ip' in kwargs and kwargs['ip']

        if contains_vk and not contains_ip:
            # We can't call get_node_from_vk if the event loop is not running, so we add it to pending commands
            if not asyncio.get_event_loop().is_running() or not self.overlay_ready:
                self.log.debugv("Cannot execute vk lookup yet as event loop is not running, or overlay is not ready."
                                " Adding func {} to command queue".format(func.__name__))
                self.manager.pending_commands.append((self, func.__name__, args, kwargs))  # TODO i think this needs to be a pending cmd on self...? not sure
                return

            cmd_id = self.manager.overlay_cli.get_node_from_vk(kwargs['vk'])
            assert cmd_id not in self.pending_lookups, "Collision! Uuid {} already in pending lookups {}".format(cmd_id, self.pending_lookups)
            self.log.debugv("Looking up vk {}, which returned command id {}".format(kwargs['vk'], cmd_id))
            self.pending_lookups[cmd_id] = (func.__name__, args, kwargs)

        # If the 'ip' key is already set in kwargs, no need to do a lookup
        else:
            func(self, *args, **kwargs)

    return _func


class LSocket:

    def __init__(self, socket: zmq.asyncio.Socket, manager: SocketManager, name='LSocket'):
        self.socket = socket
        self.manager = manager
        self.log = get_logger(name)

        self.pending_commands = {}  # A dict of 'vk' -> List(tuples), where each tuple represents a command execution
        self.pending_lookups = {}  # A dict of event_id to tuple, where the tuple again represents a command execution

    def handle_overlay_event(self, event: dict):
        assert event['event_id'] in self.pending_lookups, "Socket got overlay event {} not in pending lookups {}"\
                                                           .format(event, self.pending_lookups)
        assert event['event'] == 'got_ip', "Socket only knows how to handle got_ip events, but got {}".format(event)

        cmd_name, args, kwargs = self.pending_lookups.pop(event['event_id'])
        kwargs['ip'] = event['ip']
        getattr(self, cmd_name)(*args, **kwargs)

    def add_handler(self, handler_func, msg_types: List[MessageBase]=None, start_listening=False) -> asyncio.Future or None:
        # TODO implement
        pass

    @vk_lookup
    def connect(self, port: int, protocol: str='tcp', ip: str='', vk: str=''):
        assert ip, "Expected ip arg to be present!"

        url = "{}://{}:{}".format(protocol, ip, port)
        self.socket.connect(url)

        if vk and vk in self.pending_commands:
            self._flush_pending_commands(vk)

    def _flush_pending_commands(self, vk):
        assert asyncio.get_event_loop().is_running(), "Event loop must be running to flush commands"
        assert self.manager.overlay_ready, "Overlay must be ready to flush commands"
        assert vk in self.pending_commands, "No key for vk {} found in self.pending_commands {}".format(vk, self.pending_commands)

        commands = self.pending_commands.pop(vk)
        self.log.debugv("Composer flushing {} commands from queue".format(len(commands)))

        for cmd_name, args, kwargs in commands:
            self.log.spam("Executing pending command {} with args {} and kwargs {}".format(cmd_name, args, kwargs))
            getattr(self, cmd_name)(*args, **kwargs)

    @staticmethod
    def _defer_func(cmd_name):
        def _capture_args(self, *args, **kwargs):
            self.pending_commands.append(cmd_name, args, kwargs)
        return _capture_args

    def __getattr__(self, item):
        self.log.spam("called __getattr__ with item {}".format(item))  # TODO remove this
        assert hasattr(self.socket, item), ""
        underlying = getattr(self.socket, item)

        # If we are accessing an attribute that does not exist in LSocket, we assume its a attribute on self.socket
        if not callable(underlying):
            return underlying
        # Otherwise, we assume its a method on self.socket
        else:
            assert item in vars(type(self.socket)), "Method named {} not found on class {}".format(item, type(self.socket))

        # If this socket is not ready (ie it has not bound/connected yet), defer execution of this method
        if not self.ready:
            self.log.debugv("Socket is not ready yet. ")
            return LSocket._defer_func(item)
        else:
            return underlying


# TODO i need to engineer a mechanism such that when this socket is ready, all the commands called on it is flushed
# this socket is ready when it has succesfully bound or connected to a URL, which means either an IP was passed in or
# a VK was resolved. How do we trigger the latter?
