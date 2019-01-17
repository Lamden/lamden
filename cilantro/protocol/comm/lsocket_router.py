from cilantro.protocol.comm.lsocket_new import LSocketBase
from cilantro.messages.envelope.envelope import Envelope
import time, asyncio
from collections import defaultdict, deque
from typing import List

# How long a Router socket will wait for a PONG after sending a PING. Should be a n^2 - 1 b/c of exponential delays
# between retries (i.e. we retry in 1, then 2, then 4, then 8 seconds and so on)
PING_TIMEOUT = 127

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

        # TODO what happens tho if you try and send a msg before you have connected to the Router??? Like VK lookup
        # is still in process???
        # 1) we could rely on retries of PING
        # 2) (more complex) we could wait until the VK lookup goes thru before
        # lets go with option 1

    def send_envelope(self, env: Envelope, header: bytes=None):
        assert header is not None, "Header must be identity frame when using send on Router sockets. Cannot be None."

        # If we received a recent PONG, go ahead and send the message immediately
        if header in self.recent_pongs and time.time() - self.recent_pongs[header] < SESSION_TIMEOUT:
            self.socket.send_multipart([header, env.serialize()])

        # Otherwise, we need to send a PING and wait for a PONG before sending the envelope
        else:
            # Cancel the timeout future if there is one already, and start a new one
            if header in self.timeout_futs:
                self.timeout_futs[header].cancel()
            self.timeout_futs[header] = asyncio.ensure_future(self._start_pong_timer(header))

            self.socket.send_multipart([header, PING])
            self.deferred_msgs[header].append(env.serialize())

    async def _start_pong_timer(self, header):
        try:
            self.__start_pong_timer(header)
        except asyncio.CancelledError:
            pass

    async def __start_pong_timer(self, header):
        wait_time = 1
        while wait_time < PING_TIMEOUT:
            self.log.spam("Waiting {} seconds before retrying PING for ID {}".format(wait_time, header))
            await asyncio.sleep(wait_time)
            self.log.debugv("Sending PING retry to ID {}".format(header))
            self.socket.send_multipart([header, PING])
            wait_time *= 2

    def _process_msg(self, msg: List[bytes]):
        assert len(msg) == 2, "Expected a msg of length 2, but got {}".format(msg)

        # If the msg is a PING or PONG, mark the client as online
        if msg[1] == PING or msg[1] == PONG:
            if msg[1] == PING:
                self.socket.send_multipart([msg[0], PONG])
            self._mark_client_as_online(msg[0])
            return False
        else:
            return True

    def _mark_client_as_online(self, client_id: bytes):
        # Remove the timeout future
        if client_id in self.timeout_futs:
            self.timeout_futs[client_id].cancel()
            del self.timeout_futs[client_id]

        # Mark the time this client was seen as available
        self.recent_pongs[client_id] = time.time()

        # Send out any queued msgs
        if client_id in self.deferred_msgs:
            for _ in range(len(self.deferred_msgs[client_id])):
                env_binary = self.deferred_msgs[client_id].popleft()
                assert type(env_binary) is bytes, "Expected deferred_msgs deque to be bytes, not {}".format(env_binary)
                self.socket.send_multipart([client_id, env_binary])
            del self.deferred_msgs[client_id]



