from cilantro.protocol.comm.lsocket_new import LSocketBase
from cilantro.messages.envelope.envelope import Envelope
import time, asyncio
from collections import defaultdict, deque

# How long a Router socket will wait for a PONG after sending a PING
PONG_TIMEOUT = 20

# How long before a 'session' with another Router client expires. After the session expires, a new PING/PONG exchange
# must occur before any messages can be sent to that client
SESSION_TIMEOUT = 1800  # 30 minutes

PING, PONG = b'PING', b'PONG'


class LSocketRouter(LSocketBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # For all 3 of below data structures, the keys are the Router socket ID of a client
        self.recent_pongs = {}  # Tracks last times a PONG was received for each client. Val is epoch time (int)
        self.deferred_msgs = defaultdict(deque)  # Messages that are awaiting a PONG before sent
        self.timeout_futs = {}  # Tracks timeouts for PONG response. Val is asyncio.Future

    def send_envelope(self, env: Envelope, header: bytes=None):
        assert header is not None, "Header must be identity frame when using send on Router sockets. Cannot be None."

        # If we received a recent PONG, go ahead and send the message immediately
        if header in self.recent_pongs and time.time() - self.recent_pongs[header] < SESSION_TIMEOUT:
            super().send_envelope(env, header)

        # Otherwise, we need to PING and wait for a PONG before sending
        else:
            # Cancel the timeout future if there is one already
            if header in self.timeout_futs:
                self.timeout_futs[header].cancel()
            self.timeout_futs[header] = asyncio.ensure_future(self.start_pong_timer(header))

            self.socket.send_multipart([header, PONG])

    async def start_pong_timer(self, header):
        pass

    # TODO overwrite the listener func
