from cilantro_ee.logger import get_logger
from cilantro_ee.protocol.overlay.server import OverlayServer
from cilantro_ee.protocol.overlay.client import OverlayClient
# from cilantro_ee.protocol.comm.lsocket import LSocket
from cilantro_ee.protocol.comm.lsocket import LSocketBase
from cilantro_ee.protocol.comm.lsocket_router import LSocketRouter
from cilantro_ee.protocol.utils.socket import SocketUtil
from cilantro_ee.utils.utils import is_valid_hex

from collections import defaultdict
import asyncio, zmq.asyncio


class SocketManager:

    def __init__(self, context):
        self.log = get_logger(type(self).__name__)

        self.context = context
        self.secure_context, self.auth = SocketUtil.secure_context(self.log, async=True)

        self.sockets = []

        # pending_lookups is a dict of 'event_id' to socket instance. We use it to track vk lookups, and the LSockets
        # instances who started them. This information helps us route overlay events to the appropriate sockets
        self.pending_lookups = {}

        # vk_lookups is a dict of 'vk' to list of tuples of form (lsocket, func_name, args, kwargs)
        # We this to reconnect sockets once nodes have come back online
        self.vk_lookups = defaultdict(list)

        # overlay_callbacks tracks LSockets who have subscribed to certain overlay events with custom handlers
        self.overlay_callbacks = defaultdict(set)

        # Instantiating an OverlayClient blocks until the OverlayServer is ready
        self.overlay_client = OverlayClient(self._handle_overlay_event, self._handle_overlay_event, ctx=self.context, start=True)

    def create_socket(self, socket_type, secure=False, domain='*', *args, name='LSocket', **kwargs) -> LSocketBase:
        assert type(socket_type) is int and socket_type > 0, "socket type must be an int greater than 0, not {}".format(socket_type)

        ctx = self.secure_context if secure else self.context
        zmq_socket = SocketUtil.create_socket(socket_type, *args, **kwargs)

        if socket_type == zmq.ROUTER:
            socket = LSocketRouter(zmq_socket, manager=self, secure=secure, domain=domain, name=name)
        else:
            socket = LSocketBase(zmq_socket, manager=self, secure=secure, domain=domain, name=name)

        self.sockets.append(socket)
        return socket

    def configure_auth(self, domain='*'):
        domain_dir = SocketUtil.get_domain_dir(domain)
        self.auth.configure_curve(domain=domain, location=domain_dir)

    def _handle_overlay_event(self, e):
        self.log.debugv("SocketManager got overlay event {}".format(e))

        # Execute socket manager specific functionality
        if e['event'] == 'authorized':
            self.configure_auth(e['domain'])

        # Forward 'got_ip' and 'not_found' events to the LSockets who initiated them
        elif e['event'] in ('got_ip', 'not_found'):
            sock = self.pending_lookups.pop(e['event_id'])
            sock.handle_overlay_event(e)

        # Forward 'node_online' events to all sockets to that they can reconnect if necessary
        elif e['event'] == 'node_online':
            for sock in self.sockets:
                sock.handle_overlay_event(e)

        # TODO proper error handling / 'bad actor' logic here
        elif e['event'] == 'unauthorized_ip':
            self.log.error("SocketManager got unauthorized_ip event {}".format(e))

        else:
            self.log.debugv("SocketManager got overlay event {} that it does not know how to handle. Ignoring."
                            .format(e['event']))

        # Now, run any custom handlers added by Worker subclasses
        if e['event'] in self.overlay_callbacks:
            self.log.spam("Custom handler(s) found for overlay event {}".format(e['event']))
            for handler in self.overlay_callbacks[e['event']]:
                handler(e)
