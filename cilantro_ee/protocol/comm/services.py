from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.logger import get_logger
import zmq
import asyncio
import json


class SocketEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, SocketStruct):
            return str(o)
        return json.JSONEncoder.default(self, o)

log = get_logger("BaseServices")


class Protocols:
    TCP = 0
    INPROC = 1
    ICP = 2
    PROTOCOL_STRINGS = ['tcp://', 'inproc://', 'icp://']

# syntactic sugar yum yum
def _socket(s: str):
    return SocketStruct.from_string(s)

class SocketStruct:
    def __init__(self, protocol: int, id: str, port: int=0):
        self.protocol = protocol
        self.id = id

        if protocol == Protocols.INPROC:
            port = 0
        self.port = port

    def zmq_url(self):
        if not self.port:
            return '{}{}'.format(Protocols.PROTOCOL_STRINGS[self.protocol], self.id)
        else:
            return '{}{}:{}'.format(Protocols.PROTOCOL_STRINGS[self.protocol], self.id, self.port)

    def __str__(self):
        return self.zmq_url()

    @classmethod
    def from_string(cls, str):
        protocol = Protocols.TCP

        for protocol_string in Protocols.PROTOCOL_STRINGS:
            if len(str.split(protocol_string)) > 1:
                protocol = Protocols.PROTOCOL_STRINGS.index(protocol_string)
                str = str.split(protocol_string)[1]

        if protocol != Protocols.INPROC:
            _id, port = str.split(':')
            port = int(port)

            return cls(protocol=protocol, id=_id, port=port)
        else:
            return cls(protocol=protocol, id=str, port=None)

    @classmethod
    def is_valid(cls, s):
        return ':' in s


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

        subscription.connect(str(socket_id))

        self.subscriptions[str(socket_id)] = subscription

    def _destroy_socket(self, socket_id: SocketStruct):
        socket = self.subscriptions.get(str(socket_id))
        if socket is not None:
            socket.close()

            del self.subscriptions[str(socket_id)]

    def remove_subscription(self, socket_id: SocketStruct):
        if self.running:
            self.to_remove.append(socket_id)
        else:
            self._destroy_socket(socket_id)

    async def serve(self):
        self.running = True

        while self.running:
            await asyncio.sleep(0)

            for address, socket in self.subscriptions.items():
                try:
                    event = await socket.poll(timeout=self.timeout, flags=zmq.POLLIN)
                    if event:
                        msg = await socket.recv()
                        self.received.append((msg, address))
                except zmq.error.ZMQError as e:
                    socket.close()

                    socket = self.ctx.socket(zmq.SUB)
                    socket.setsockopt(zmq.SUBSCRIBE, b'')
                    socket.setsockopt(zmq.LINGER, self.linger)

                    socket.connect(str(address))

            # Destory sockets async
            for address in self.to_remove:
                self._destroy_socket(address)
            self.to_remove = []

    def stop(self):
        self.running = False


class RequestReplyService:
    def __init__(self, socket_id: SocketStruct, wallet: Wallet, ctx: zmq.Context, linger=2000, poll_timeout=2000):
        self.address = str(socket_id)
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
            try:
                event = await self.socket.poll(timeout=self.poll_timeout, flags=zmq.POLLIN)
                if event:
                    msg = await self.socket.recv()
                    result = self.handle_msg(msg)

                    if result is None:
                        result = b''

                    await self.socket.poll(timeout=self.poll_timeout, flags=zmq.POLLOUT)
                    await self.socket.send(result)

            except zmq.error.ZMQError as e:
                self.socket = self.ctx.socket(zmq.REP)
                self.socket.setsockopt(zmq.LINGER, self.linger)
                self.socket.bind(self.address)

        self.socket.close()

    def handle_msg(self, msg):
        return msg

    def stop(self):
        self.running = False


async def get(socket_id: SocketStruct, msg: bytes, ctx:zmq.Context, timeout=500, linger=2000, retries=10):
    if retries <= 0:
        return None

    socket = ctx.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, linger)
    try:
        # Allow passing an existing socket to save time on initializing a new one and waiting for connection.
        socket.connect(str(socket_id))

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
        socket.close()
        return await get(socket_id, msg, ctx, timeout, linger, retries-1)


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
        log.info(str(e))
        return None


class Mailbox:
    def __init__(self, socket_id: SocketStruct, wallet: Wallet, ctx: zmq.Context, linger=2000, poll_timeout=2000):
        self.backend_address = str(socket_id)

        socket_id.id = '*'

        self.frontend_address = str(socket_id)

        self.wallet = wallet
        self.ctx = ctx

        self.frontend = None
        self.backend = None

        self.linger = linger
        self.poll_timeout = poll_timeout

        self.running = False

    async def serve(self):
        self.setup_frontend()
        self.setup_backend()

        self.running = True

        while self.running:
            try:
                event = await self.frontend.poll(timeout=self.poll_timeout, flags=zmq.POLLIN)
                if event:
                    _id, msg = await self.frontend.recv_multipart()
                    result = asyncio.ensure_future(self.handle_msg(msg))
                    result.add_callback(self.return_msg)

            except zmq.error.ZMQError:
                self.setup_frontend()

        self.frontend.close()
        self.backend.close()

    async def handle_msg(self, _id, msg):
        return msg

    async def return_msg(self, future: asyncio.Future):
        _id, msg = future.result()

        sent = False
        while not sent:
            try:
                await self.backend.send_multipart([_id, msg])
                sent = True
            except zmq.error.ZMQError:
                self.setup_backend()

    def setup_backend(self):
        self.backend = self.ctx.socket(zmq.DEALER)
        self.backend.setsockopt(zmq.LINGER, self.linger)
        self.backend.bind(self.backend_address)

    def setup_frontend(self):
        self.frontend = self.ctx.socket(zmq.ROUTER)
        self.frontend.setsockopt(zmq.LINGER, self.linger)
        self.frontend.bind(self.frontend_address)

    def stop(self):
        self.running = False
