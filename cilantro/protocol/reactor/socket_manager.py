import zmq.asyncio
import asyncio
from cilantro.protocol.overlay.interface import OverlayServer, OverlayClient
from cilantro.protocol.reactor.lsocket import LSocket
from cilantro.logger import get_logger
from collections import deque
from cilantro.constants.overlay_network import CLIENT_SETUP_TIMEOUT
from cilantro.utils.utils import is_valid_hex
from cilantro.protocol import wallet
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.base.base import MessageBase
from cilantro.protocol.structures import EnvelopeAuth



# TODO Better name for SocketManager? SocketManager is also responsible for handling the OverlayClient, so maybe we
# should name it something that makes that more obvious
class SocketManager:

    def __init__(self, signing_key: str, context=None, loop=None, start_overlay_client=True):
        assert is_valid_hex(signing_key, 64), "signing_key must a 64 char hex str not {}".format(signing_key)

        self.log = get_logger(type(self).__name__)

        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)

        self.loop = loop or asyncio.get_event_loop()
        self.context = context or zmq.asyncio.Context()

        self.sockets = []
        self.pending_lookups = {}   # A dict of 'event_id' to socket instance
        self.pending_commands = deque()  # To hold pending_lookups until the overlay client is ready

        # Configure overlay interface
        self.overlay_client = OverlayClient(self._handle_overlay_event, loop=self.loop, ctx=self.context)
        self.overlay_ready = False

        # Listen to overlay events, and check the overlay status. The SocketManager should defer executing any commands
        # involving vk lookups until the overlay is ready. If start_overlay_client=True, then we start the future to
        # ask the overlay service if it is ready. We wrap _check_overlay_status in a Future so that it can be run when
        # the event loop starts. If the event loop is not running when _check_overlay_status is called, this class
        # will have no way of receiving the callback from the OverlayServer.
        # If start_overlay_client is not set,
        if start_overlay_client:
            asyncio.ensure_future(self._check_overlay_status())

        # Create a future to ensure the overlay server is ready in a reasonable amount of time, and blow up if it isn't
        self.timeout_future = asyncio.ensure_future(self._enforce_client_ready())

    def create_socket(self, socket_type, *args, **kwargs) -> LSocket:
        assert type(socket_type) is int and socket_type > 0, "socket type must be an int greater than 0, not {}".format(socket_type)

        zmq_socket = self.context.socket(socket_type, *args, **kwargs)
        socket = LSocket(zmq_socket, manager=self)
        self.sockets.append(socket)

        return socket

    async def _enforce_client_ready(self):
        await asyncio.sleep(CLIENT_SETUP_TIMEOUT)
        if not self.overlay_ready:
            msg = "Timed out waiting for overlay server! Did not receive a ready signal from overlay server in {} " \
                  "seconds".format(CLIENT_SETUP_TIMEOUT)
            # TODO is it necessary to log this in addition to raising an error?
            # I'm paranoid raising an Exception might get swallowed somewhere
            self.log.fatal(msg)
            raise Exception(msg)  # TODO i dont think this properly blow up this process b/c we are in a coro right now

    async def _check_overlay_status(self):
        # self.log.debug("Checking overlay status")
        self.log.important("Checking overlay status")  # TODO remove
        self.overlay_client.get_service_status()

    def _handle_overlay_event(self, e):
        self.log.spam("SocketManager got overlay event {}".format(e))
        self.log.important2("SocketManager got overlay event {}".format(e))  # TODO remove

        if e['event'] == 'service_started' or (e['event'] == 'service_status' and e['status'] == 'ready'):
            if self.overlay_ready:
                self.log.debugv("Overlay is already ready. Not flushing commands")
                return

            self.log.notice("Overlay service ready!")
            self.overlay_ready = True
            self.timeout_future.cancel()
            self._flush_pending_commands()
            return

        elif e['event'] == 'got_ip':
            assert e['event_id'] in self.pending_lookups, "Overlay returned event id that is not in pending_commands!"

            sock = self.pending_lookups.pop(e['event_id'])
            sock.handle_overlay_event(e)

        else:
            # TODO handle all events. Or write code to only subscribe to certain events
            self.log.warning("Composer got overlay event {} that it does not know how to handle. Ignoring.".format(e))
            return

    def _flush_pending_commands(self):
        assert asyncio.get_event_loop().is_running(), "Event loop must be running to flush commands"
        assert self.overlay_ready, "Overlay must be ready to flush commands"

        self.log.debugv("SocketManager flushing {} commands from queue".format(len(self.pending_commands)))

        try:
            for socket, cmd_name, args, kwargs in self.pending_commands:
                self.log.spam("Executing pending command {} on socket {} with args {} and kwargs {}".format(cmd_name, socket, args, kwargs))
                getattr(socket, cmd_name)(*args, **kwargs)
        except Exception as e:
            self.log.fatal("wtf:\n{}".format(e))

        self.pending_commands.clear()

