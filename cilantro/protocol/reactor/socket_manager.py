from cilantro.logger import get_logger
from cilantro.protocol.overlay.daemon import OverlayServer, OverlayClient
from cilantro.protocol.reactor.lsocket import LSocket
from cilantro.protocol.overlay.auth import Auth
from cilantro.utils.utils import is_valid_hex

from collections import defaultdict
import asyncio, zmq.asyncio


class SocketManager:

    def __init__(self, signing_key: str, context=None, loop=None):
        assert is_valid_hex(signing_key, 64), "signing_key must a 64 char hex str not {}".format(signing_key)

        self.log = get_logger(type(self).__name__)

        Auth.setup(signing_key, reset_auth_folder=False)

        self.signing_key = Auth.sk
        self.verifying_key = Auth.vk
        self.public_key = Auth.public_key
        self.secret = Auth.private_key

        self.loop = loop or asyncio.get_event_loop()
        self.context = context or zmq.asyncio.Context()
        self.secure_context, self.auth = Auth.secure_context(async=True)

        self.sockets = []
        self.pending_lookups = {}   # A dict of 'event_id' to socket instance
        self.overlay_callbacks = defaultdict(set)

        # Instantiating an OverlayClient blocks until the OverlayServer is ready
        self.overlay_client = OverlayClient(self._handle_overlay_event, loop=self.loop, ctx=self.context, start=True)

    def create_socket(self, socket_type, secure=False, domain='*', *args, name='LSocket', **kwargs) -> LSocket:
        assert type(socket_type) is int and socket_type > 0, "socket type must be an int greater than 0, not {}".format(socket_type)

        ctx = self.secure_context if secure else self.context
        zmq_socket = ctx.socket(socket_type, *args, **kwargs)

        socket = LSocket(zmq_socket, manager=self, secure=secure, domain=domain, name=name)
        self.sockets.append(socket)

        return socket

    def _handle_overlay_event(self, e):
        self.log.debugv("SocketManager got overlay event {}".format(e))

        # Execute socket manager specific functionality
        if e['event'] == 'authorized':
            Auth.configure_auth(self.auth, e['domain'])
        elif e['event'] == 'got_ip':
            sock = self.pending_lookups.pop(e['event_id'])
            sock.handle_overlay_event(e)
        else:
            self.log.debugv("SocketManager got overlay event {} that it does not know how to handle. Ignoring."
                            .format(e['event']))

        # Now, run any custom handlers added by Worker subclasses
        if e['event'] in self.overlay_callbacks:
            self.log.debugv("Custom handler(s) found for overlay event {}".format(e['event']))
            for handler in self.overlay_callbacks[e['event']]:
                handler(e)
