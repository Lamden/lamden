from cilantro.logger import get_logger
from cilantro.protocol import wallet
from cilantro.protocol.reactor.socket_manager import SocketManager
from cilantro.protocol.reactor.lsocket import LSocket

import asyncio, os
import zmq.asyncio

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class Worker:

    def __init__(self, signing_key, name=''):
        name = name or type(self).__name__
        self.log = get_logger(name)

        # Create a new event loop for this process
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.context = zmq.asyncio.Context()

        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)

        self.manager = SocketManager(signing_key=signing_key, context=self.context, loop=self.loop)

