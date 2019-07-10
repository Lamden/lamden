from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.logger import get_logger
import zmq
import asyncio


log = get_logger("BaseServices")


class Protocols:
    TCP = 0
    INPROC = 1
    ICP = 2
    PROTOCOL_STRINGS = ['tcp://', 'inproc://', 'icp://']


class SocketStruct:
    def __init__(self, protocol: int, id: str, port: int):
        self.protocol = protocol
        self.id = id

        if protocol == Protocols.INPROC:
            port = None
        self.port = port

    def zmq_url(self):
        if self.port is None:
            return '{}{}'.format(Protocols.PROTOCOL_STRINGS[self.protocol], self.id)
        else:
            return '{}{}:{}'.format(Protocols.PROTOCOL_STRINGS[self.protocol], self.id, self.port)


# Pushes current task to the back of the event loop
async def defer():
    await asyncio.sleep(0)


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

    def add_subscription(self, socket_id: SocketStruct, filter=b''):
        subscription = self.ctx.socket(zmq.SUB)
        subscription.setsockopt(zmq.SUBSCRIBE, filter)
        subscription.setsockopt(zmq.LINGER, self.linger)

        address = socket_id.zmq_url()

        subscription.connect(address)

        self.subscriptions[address] = subscription

    def _destroy_socket(self, socket_struct: SocketStruct):
        address = socket_struct.zmq_url()
        socket = self.subscriptions.get(address)
        if socket is not None:
            socket.close()

            del self.subscriptions[address]

    def remove_subscription(self, socket_id: SocketStruct):
        address = socket_id.zmq_url()
        if self.running:
            self.to_remove.append(address)
        else:
            self._destroy_socket(address)

    async def serve(self):
        self.running = True

        while self.running:
            await asyncio.sleep(0)

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
    def __init__(self, socket_id: SocketStruct, wallet: Wallet, ctx: zmq.Context, linger=2000, poll_timeout=2000):
        self.address = socket_id.zmq_url()
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


async def get(socket_id: SocketStruct, msg: bytes, ctx:zmq.Context, timeout=500, linger=2000):
    try:
        # Allow passing an existing socket to save time on initializing a new one and waiting for connection.
        socket = ctx.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, linger)

        socket.connect(socket_id.zmq_url())

        await socket.send(msg)

        event = await socket.poll(timeout=timeout, flags=zmq.POLLIN)
        if event:
            response = await socket.recv()

            socket.close()

            return response
        else:
            socket.close()
            return None
    except Exception as e:
        log.critical('Get exception thrown: {}'.format(str(e)))
        socket.close()
        return None


class DataFormat:
    RAW = 0
    STRING = 1
    JSON = 2
    MULTIPART = 3
    PYOBJ = 4
    SERIALIZED = 5


def send_recv_funcs_for_format(format: int, socket: zmq.Socket):
    functions = [(socket.send, socket.recv),
                 (socket.send_string, socket.recv_string),
                 (socket.send_json, socket.recv_json),
                 (socket.send_multipart, socket.recv_multipart),
                 (socket.send_pyobj, socket.recv_pyobj),
                 (socket.send_serialized, socket.recv_serialized)]

    return functions[format]


# Graceful request from ZMQ socket. Should be expanded to support sending types
async def _get(socket: zmq.Socket, msg, timeout=500, format=DataFormat.RAW):
    send, recv = send_recv_funcs_for_format(format, socket)
    try:
        await send(msg)

        event = await socket.poll(timeout=timeout, flags=zmq.POLLIN)
        if event:
            response = await recv()

            return response
        else:
            return None
    except Exception as e:
        return None