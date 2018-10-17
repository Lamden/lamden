import zmq.asyncio
import asyncio
from cilantro.protocol.overlay.daemon import OverlayServer, OverlayClient
from cilantro.protocol.reactor.lsocket import LSocket
from cilantro.logger import get_logger
from collections import deque
from cilantro.constants.overlay_network import CLIENT_SETUP_TIMEOUT
from cilantro.utils.utils import is_valid_hex
from cilantro.protocol import wallet
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.base.base import MessageBase
from cilantro.protocol.structures import EnvelopeAuth

from cilantro.protocol.overlay.auth import Auth
from nacl.bindings import crypto_sign_ed25519_sk_to_curve25519
from nacl.signing import SigningKey

# TODO Better name for SocketManager? SocketManager is also responsible for handling the OverlayClient, so maybe we
# should name it something that makes that more obvious
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

        if e['event'] == 'got_ip':
            assert e['event_id'] in self.pending_lookups, "Overlay returned event {} that is not in pending_lookups {}!"\
                                                          .format(e, self.pending_lookups)

            sock = self.pending_lookups.pop(e['event_id'])
            sock.handle_overlay_event(e)
        elif e['event'] == 'authorized':
            Auth.configure_auth(self.auth, e['domain'])
        else:
            # TODO handle all events. Or write code to only subscribe to certain events
            self.log.warning("Composer got overlay event {} that it does not know how to handle. Ignoring.".format(e))
            return
