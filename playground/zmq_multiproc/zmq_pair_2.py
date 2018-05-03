"""
CLIENT
"""

import asyncio
import zmq
import zmq.asyncio
import random
import sys
import time

port = "5556"
# url = "tcp://localhost:%s" % port
url = "ipc://helloletsgo"
context = zmq.asyncio.Context()
socket = context.socket(zmq.PAIR)
socket.connect(url)

async def client():
    print("Starting CLIENT on url {}...".format(url))
    while True:
        msg = await socket.recv()
        print(msg)
        socket.send(b"client message to server1")
        socket.send(b"client message to server2")
        await asyncio.sleep(1)


loop = asyncio.get_event_loop()
loop.run_until_complete(client())