"""
SERVER
"""
import signal
import asyncio
import zmq
import zmq.asyncio
import random
import sys
import time
from multiprocessing import Process
from cilantro.logger import get_logger

port = "5556"
# url = "tcp://*:%s" % port
url = "ipc://helloletsgo55"

def start_server():
    async def server():
        log.info("Starting SERVER on url {}...".format(url))
        while True:
            log.debug("Sending to client3")
            socket.send(b"Server message to client3")
            log.debug("Awaiting recv")
            msg = await socket.recv()
            log.debug(msg)
            await asyncio.sleep(1)

    log = get_logger("Server")
    log.info("Server proc started")
    context = zmq.asyncio.Context()
    socket = context.socket(zmq.PAIR)
    socket.bind(url)

    log.debug("Starting child proc")
    client_p = Process(target=start_client, args=(context,))
    client_p.start()

    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server())

def start_client(context=None):
    async def client():
        log.info("Starting CLIENT on url {}...".format(url))
        # context = context or zmq.asyncio.Context()
        log.info("ss")
        socket = context.socket(zmq.PAIR)
        log.info("dd")
        socket.connect(url)
        while True:
            log.debug("Awaiting recv")
            msg = await socket.recv()
            log.debug(msg)
            log.debug("Double sending")
            socket.send(b"client message to server1")
            socket.send(b"client message to server2")
            await asyncio.sleep(1)

    log = get_logger("Client")
    log.info("Client proc started")
    context = zmq.asyncio.Context()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client())


if __name__ == "__main__":
    start_server()