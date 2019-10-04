from cilantro_ee.core.sockets.lsocket import LSocketBase
import time, asyncio
from collections import defaultdict, deque
from typing import List

# How long a Router socket will wait for a PONG after sending a PING. Should be a n^2 - 1 b/c of exponential delays
# between retries (i.e. we retry in 1, then 2, then 4, then 8 seconds and so on)
PING_TIMEOUT = 127

# How long before a 'session' with another Router client expires. After the session expires, a _new PING/PONG exchange
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

    async def _start_ping_timer(self, header):
        try:
            await self.__start_ping_timer(header)
        except asyncio.CancelledError:
            pass

    async def __start_ping_timer(self, header):
        wait_time = 1
        while wait_time < PING_TIMEOUT:
            self.log.spam("Waiting {} seconds before retrying PING for ID {}".format(wait_time, header))
            await asyncio.sleep(wait_time)
            self.log.debugv("Sending PING retry to ID {}".format(header))
            self.socket.send_multipart([header, PING])
            wait_time *= 2

        assert header in self.timeout_futs, "PING_TIMEOUT reached but header {} was delete from timeout_futs {}. so " \
                                            "(it should have been cancelled)".format(header, self.timeout_futs)
        # TODO do we have to make sure its not canceled? Can i gaurentee this code wont run if .cancel() is called
        # on this future??

        self.log.warning("Ping timed out for Router socket to node with id {}".format(id))
        # TODO -- close connection corresponding to this id if we opened it to clean up and prevent leaks

    def _process_msg(self, msg: List[bytes]) -> bool:
        # If message length is not 2, we assume its an IPC msg, and return True.
        # TODO -- more robust logic here. Can we maybe set a flag on the sock indicating its an IPC socket?
        if len(msg) != 2:
            return True

        self._mark_client_as_online(msg[0])  # Mark the client as online, regardless of what message they sent

        if msg[1] == PING or msg[1] == PONG:
            if msg[1] == PING:
                self.log.spam("Replying to PING from client with ID {}".format(msg[0]))
                self.socket.send_multipart([msg[0], PONG])
            return False
        else:
            return True

    def _mark_client_as_online(self, client_id: bytes):
        self.log.spam("Marking client with ID {} as online".format(client_id))

        # Remove the timeout future
        if client_id in self.timeout_futs:
            self.timeout_futs[client_id].cancel()
            del self.timeout_futs[client_id]

        # Mark the time this client was seen as available
        self.recent_pongs[client_id] = time.time()

        # Send out any queued msgs
        if client_id in self.deferred_msgs:
            self.log.debugv("Flushing {} deferred messages from client with ID {}"
                            .format(len(self.deferred_msgs[client_id]), client_id))
            for _ in range(len(self.deferred_msgs[client_id])):
                env_binary = self.deferred_msgs[client_id].popleft()
                assert type(env_binary) is bytes, "Expected deferred_msgs deque to be bytes, not {}".format(env_binary)
                self.socket.send_multipart([client_id, env_binary])
            del self.deferred_msgs[client_id]
