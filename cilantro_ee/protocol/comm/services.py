from cilantro_ee.protocol.wallet import Wallet
import zmq


class SubscriptionService:
    def __init__(self, ctx: zmq.Context, timeout=100, linger=2000):
        # Socket constants
        self.ctx = ctx
        self.timeout = timeout
        self.linger = linger

        # State variables
        self.subscriptions = {}
        self.running = False

        # Async queues
        self.received = []
        self.to_remove = []

    def add_subscription(self, address, filter=b''):
        subscription = self.ctx.socket(zmq.SUB)
        subscription.setsockopt(zmq.SUBSCRIBE, filter)
        subscription.setsockopt(zmq.LINGER, self.linger)
        subscription.connect(address)

        self.subscriptions[address] = subscription

    def _destroy_socket(self, address):
        socket = self.subscriptions.get(address)
        if socket is not None:
            socket.close()

            del self.subscriptions[address]

    def remove_subscription(self, address):
        if self.running:
            self.to_remove.append(address)
        else:
            self._destroy_socket(address)

    async def serve(self):
        self.running = True

        while self.running:
            for address, socket in self.subscriptions.items():
                event = await socket.poll(timeout=self.timeout, flags=zmq.POLLIN)
                if event:
                    msg = await socket.recv()
                    self.received.append((msg, address))

            # Destory sockets async
            for address in self.to_remove:
                self._destroy_socket(address)
            self.to_remove = []

    def stop(self):
        self.running = False


class RequestReplyService:
    def __init__(self, address: str, wallet: Wallet, ctx: zmq.Context, linger=2000, poll_timeout=2000):
        self.address = address
        self.wallet = wallet
        self.ctx = ctx

        self.socket = None

        self.linger = linger
        self.poll_timeout = poll_timeout

        self.running = False

    async def serve(self):
        self.socket = self.ctx.socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, self.linger)
        self.socket.bind(self.address)

        self.running = True

        while self.running:
            event = await self.socket.poll(timeout=self.poll_timeout, flags=zmq.POLLIN)
            if event:
                msg = await self.socket.recv()

                result = self.handle_msg(msg)

                if result is None:
                    result = b''

                await self.socket.send(result)

        self.socket.close()

    def handle_msg(self, msg):
        return msg

    def stop(self):
        self.running = False


async def get(address: str, msg: bytes, ctx:zmq.Context, timeout=500, linger=2000):
    try:
        socket = ctx.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, linger)

        socket.connect(address)

        await socket.send(msg)

        event = await socket.poll(timeout=timeout, flags=zmq.POLLIN)
        if event:
            response = await socket.recv()

            socket.close()

            return response
        else:
            return None
    except Exception as e:
        return None