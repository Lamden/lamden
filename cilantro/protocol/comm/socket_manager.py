from cilantro.logger import get_logger
from cilantro.protocol.overlay.daemon import OverlayServer, OverlayClient
# from cilantro.protocol.comm.lsocket import LSocket
from cilantro.protocol.comm.lsocket import LSocketBase
from cilantro.protocol.comm.lsocket_router import LSocketRouter
from cilantro.protocol.comm.socket_auth import SocketAuth
from cilantro.utils.keys import Keys
from cilantro.utils.utils import is_valid_hex

from collections import defaultdict
import asyncio, zmq.asyncio


class SocketManager:

    def __init__(self, signing_key: str, context=None, loop=None):
        assert is_valid_hex(signing_key, 64), "signing_key must a 64 char hex str not {}".format(signing_key)

        self.log = get_logger(type(self).__name__)

        Keys.setup(signing_key, reset_auth_folder=False)

        self.signing_key = Keys.sk
        self.verifying_key = Keys.vk
        self.public_key = Keys.public_key
        self.secret = Keys.private_key

        self.loop = loop or asyncio.get_event_loop()
        self.context = context or zmq.asyncio.Context()
        self.secure_context, self.auth = SocketAuth.secure_context(async=True)

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
        self.overlay_client = OverlayClient(self._handle_overlay_event, loop=self.loop, ctx=self.context, start=True)

    def set_new_node_tracking(self):
        self.overlay_client.set_new_node_tracking()

    def create_socket(self, socket_type, secure=False, domain='*', *args, name='LSocket', **kwargs) -> LSocketBase:
        assert type(socket_type) is int and socket_type > 0, "socket type must be an int greater than 0, not {}".format(socket_type)

        ctx = self.secure_context if secure else self.context
        zmq_socket = ctx.socket(socket_type, *args, **kwargs)

        if socket_type == zmq.ROUTER:
            socket = LSocketRouter(zmq_socket, manager=self, secure=secure, domain=domain, name=name)
        else:
            socket = LSocketBase(zmq_socket, manager=self, secure=secure, domain=domain, name=name)

        self.sockets.append(socket)
        return socket

    def _handle_overlay_event(self, e):
        self.log.debugv("SocketManager got overlay event {}".format(e))

        # Execute socket manager specific functionality
        if e['event'] == 'authorized':
            SocketAuth.configure_auth(self.auth, e['domain'])

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
