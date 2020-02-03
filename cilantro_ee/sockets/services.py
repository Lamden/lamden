from cilantro_ee.logger.base import get_logger
import zmq
import asyncio
from zmq.utils import monitor
import pathlib
from zmq.auth.certs import load_certificate

from cilantro_ee.sockets.struct import SocketStruct

log = get_logger("BaseServices")


async def get(socket_id: SocketStruct, msg: bytes, ctx:zmq.Context, timeout=1000, linger=500, retries=10, dealer=False):
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

            socket.close()

            return response
        else:
            socket.close()
            return None
    except Exception as e:
        socket.close()
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
        socket.close()
        return True, evnt_dict['endpoint'].decode()

    # Otherwise, close the socket. Return result and the socket for further processing / updating sockets
    socket.close()
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

    server_pub, _ = load_certificate(str(cert_dir / f'{server_vk.hex()}.key'))

    socket.curve_serverkey = server_pub

    s = socket.get_monitor_socket()

    # Try to connect
    socket.connect(str(socket_id))

    # See if the connection was successful
    evnt = await s.recv_multipart()
    evnt_dict = monitor.parse_monitor_message(evnt)

    # If so, shoot out the message
    if evnt_dict['event'] == 1:
        socket.send(msg, flags=zmq.NOBLOCK)
        socket.close()
        return True, evnt_dict['endpoint'].decode()

    # Otherwise, close the socket. Return result and the socket for further processing / updating sockets
    socket.close()
    return False, evnt_dict['endpoint'].decode()


async def secure_multicast(wallet, ctx, msg: bytes, peers: tuple, cert_dir='cilsocks'):
    return await asyncio.gather(*[
        secure_send_out(
            wallet=wallet,
            ctx=ctx,
            msg=msg,
            socket_id=ip,
            server_vk=vk,
            cert_dir=cert_dir
        ) for ip, vk in peers
    ])
