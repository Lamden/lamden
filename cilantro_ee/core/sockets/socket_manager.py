from cilantro_ee.core.logger import get_logger
from cilantro_ee.services.overlay.server import OverlayServer
from cilantro_ee.services.overlay.client import OverlayClient
from cilantro_ee.core.sockets.lsocket import LSocketBase
from cilantro_ee.core.sockets.lsocket_router import LSocketRouter
from cilantro_ee.core.sockets.socket import SocketUtil
from cilantro_ee.utils.utils import is_valid_hex
from cilantro_ee.services.storage.vkbook import VKBook

from collections import defaultdict
import asyncio, zmq.asyncio, time


class SocketManager:

    def __init__(self, context):
        self.log = get_logger(type(self).__name__)

        self.vkbook = VKBook()

        self.context = context
        self.secure_context, self.auth = SocketUtil.secure_context(self.log, async=True)

        self.sockets = []

        self.num_delegates_joined_since_last = 0

        # pending_lookups is a dict of 'event_id' to socket instance. We use it to track vk lookups, and the LSockets
        # instances who started them. This information helps us route overlay events to the appropriate sockets
        self.pending_lookups = {}

        # vk_lookups is a dict of 'vk' to list of tuples of form (lsocket, func_name, args, kwargs)
        # We this to reconnect sockets once nodes have come back online
        self.tracking_vks = defaultdict(list)

        # overlay_callbacks tracks LSockets who have subscribed to certain overlay events with custom handlers
        self.overlay_callbacks = defaultdict(set)

        self._ready = False

        # Instantiating an OverlayClient blocks until the OverlayServer is ready
        self.overlay_client = OverlayClient(self._handle_overlay_reply, self._handle_overlay_event, ctx=self.context)


    def is_ready(self):
        return self._ready
    

    def create_socket(self, socket_type, secure=False, domain='*', *args, name='LSocket', **kwargs) -> LSocketBase:
        assert type(socket_type) is int and socket_type > 0, "socket type must be an int greater than 0, not {}".format(socket_type)

        secure = False    # temporarily disable

        ctx = self.secure_context if secure else self.context
        zmq_socket = SocketUtil.create_socket(ctx, socket_type, *args, **kwargs)

        if socket_type == zmq.ROUTER:
            socket = LSocketRouter(zmq_socket, manager=self, secure=secure, domain=domain, name=name)
        else:
            socket = LSocketBase(zmq_socket, manager=self, secure=secure, domain=domain, name=name)

        self.sockets.append(socket)
        return socket

    def get_and_reset_num_delegates_joined(self):
        nd = min(self.num_delegates_joined_since_last, len(self.vkbook.delegates))
        self.num_delegates_joined_since_last = 0
        return nd

    def configure_auth(self, domain='*'):
        domain_dir = SocketUtil.get_domain_dir(domain)
        # self.auth.configure_curve(domain=domain, location=domain_dir)

    def _handle_overlay_reply(self, e):
        self.log.debugv("SocketManager got overlay reply {}".format(e))

        if e['event_id'] in self.pending_lookups:
            sock = self.pending_lookups.pop(e['event_id'])

            sock.handle_overlay_reply(e)

            if (e['event'] == 'got_ip') and (e['vk'] in self.vkbook.delegates):
                self.num_delegates_joined_since_last += 1
        else:
            self.log.debugv("SocketManager got overlay reply {} that is not a "
                            "pending request. Ignoring.".format(e['event']))

    def _handle_overlay_event(self, e):
        self.log.debugv("SocketManager got overlay event {}".format(e))

        if (e['event'] == 'service_status') and (e['status'] == 'ready'):
            self.log.info("Overlay Server ready!!!")
            self._ready = True

        # Forward 'node_online' events to the subscribing sockets so that they can reconnect if necessary
        elif (e['event'] == 'node_online') and (e['vk'] in self.tracking_vks):
            for sock in self.tracking_vks[e['vk']]:
                sock.handle_overlay_event(e)
            if (e['vk'] in self.vkbook.delegates):
                self.num_delegates_joined_since_last += 1

        else:
            self.log.debugv("SocketManager got an event {} that it does not "
                            "know how to handle. Ignoring.".format(e['event']))

        # Now, run any custom handlers added by Worker subclasses
        if e['event'] in self.overlay_callbacks:
            self.log.spam("Custom handler(s) found for overlay event {}".format(e['event']))
            for handler in self.overlay_callbacks[e['event']]:
                handler(e)
