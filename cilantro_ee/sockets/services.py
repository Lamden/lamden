from cilantro_ee.logger.base import get_logger
import zmq
import asyncio
from zmq.utils import monitor
import pathlib
from zmq.auth.certs import load_certificate

from cilantro_ee.sockets.struct import SocketStruct

log = get_logger("BaseServices")

class Outbox:
    def __init__(self, ctx: zmq.Context):
        self.sockets = {}
        self.ctx = ctx

    def get_socket(self, socket_id, _type=zmq.DEALER, linger=500):
        socket = self.sockets.get(str(socket_id))

        # Connect and store if it doesn't exist
        if socket is None:
            socket = self.ctx.socket(_type)
            socket.connect(str(socket_id))
            socket.setsockopt(zmq.LINGER, linger)
            self.sockets[str(socket_id)] = socket

        return socket

    async def get(self, socket_id, msg, timeout=1000):
        socket = self.get_socket(socket_id, zmq.REQ)
        await socket.send(msg)

        event = await socket.poll(timeout=timeout, flags=zmq.POLLIN)
        if event:
            response = await socket.recv()

            return response
        return None


async def get(socket_id: SocketStruct, msg: bytes, ctx:zmq.Context, timeout=1000, linger=500, retries=10, dealer=True):
    if retries < 0:
        return None

    if dealer:
        socket = ctx.socket(zmq.DEALER)
    else:
        socket = ctx.socket(zmq.REQ)

    socket.setsockopt(zmq.LINGER, linger)
    try:
        # Allow passing an existing socket to save time on initializing a _new one and waiting for connection.
        socket.connect(str(socket_id))

        await socket.send(msg)

        event = await socket.poll(timeout=timeout, flags=zmq.POLLIN)
        if event:
            response = await socket.recv()

            socket.disconnect(str(socket_id))

            return response
        else:
            socket.disconnect(str(socket_id))
            return None
    except Exception as e:
        socket.disconnect(str(socket_id))
        return await get(socket_id, msg, ctx, timeout, linger, retries-1)


async def send_out(ctx, msg, socket_id):
    # Setup a socket and its monitor
    socket = ctx.socket(zmq.DEALER)
    s = socket.get_monitor_socket()

    # Try to connect
    socket.connect(str(socket_id))

    # See if the connection was successful
    evnt = await s.recv_multipart()
    evnt_dict = monitor.parse_monitor_message(evnt)

    # If so, shoot out the message
    if evnt_dict['event'] == 1:
        socket.send(msg, flags=zmq.NOBLOCK)
        socket.disconnect(str(socket_id))
        return True, evnt_dict['endpoint'].decode()

    # Otherwise, close the socket. Return result and the socket for further processing / updating sockets
    socket.disconnect(str(socket_id))
    return False, evnt_dict['endpoint'].decode()


async def multicast(ctx, msg: bytes, peers: list):
    return await asyncio.gather(*[send_out(ctx, msg, p) for p in peers])


async def secure_send_out(wallet, ctx, msg, socket_id, server_vk, cert_dir='cilsocks'):
    # Setup a socket and its monitor
    socket = ctx.socket(zmq.DEALER)

    socket.curve_secretkey = wallet.curve_sk
    socket.curve_publickey = wallet.curve_vk

    cert_dir = pathlib.Path.home() / cert_dir
    cert_dir.mkdir(parents=True, exist_ok=True)

    server_pub, _ = load_certificate(str(cert_dir / f'{server_vk}.key'))

    socket.curve_serverkey = server_pub

    s = socket.get_monitor_socket()

    # Try to connect
    socket.connect(str(socket_id))

    event = 2
    evnt_dict = {}
    while event == 2:
        evnt = await s.recv_multipart()
        evnt_dict = monitor.parse_monitor_message(evnt)
        event = evnt_dict['event']

    # If so, shoot out the message
    if event == 1:
        socket.send(msg, flags=zmq.NOBLOCK)
        socket.disconnect(str(socket_id))
        return True, evnt_dict['endpoint'].decode()

    # Otherwise, close the socket. Return result and the socket for further processing / updating sockets
    socket.disconnect(str(socket_id))
    return False, evnt_dict['endpoint'].decode()


async def secure_multicast(wallet, ctx, msg: bytes, peers: list, cert_dir='cilsocks'):
    return await asyncio.gather(*[
        secure_send_out(
            wallet=wallet,
            ctx=ctx,
            msg=msg,
            socket_id=peer[1],
            server_vk=peer[0],
            cert_dir=cert_dir
        ) for peer in peers
    ])
