from cilantro.logger.base import get_logger
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.base.base import MessageBase
from cilantro.protocol import wallet

from cilantro.protocol.reactor.socket_manager import SocketManager
from cilantro.protocol.reactor.lsocket import LSocket

import asyncio
import zmq.asyncio
import time


PORT = 9432
PROTOCOL = 'tcp'


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


class Tester:

    def __init__(self, signing_key, name):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.ctx = zmq.asyncio.Context()
        self.signing_key = signing_key
        self.log = get_logger((name))

        self.manager = SocketManager(signing_key=signing_key, context=self.ctx, loop=self.loop)

        self.sock = None

    def start_pubbing(self, ip, num_msgs=50):
        async def _start_pubbing(num):
            for i in range(num):
                self.log.info("sending pub {}".format(i))
                self.sock.send_multipart([b'', 'hello #{}'.format(i).encode()])
                await asyncio.sleep(1)

        self.sock = self.manager.create_socket(zmq.PUB)
        self.log.socket("binding pub socket")
        self.sock.bind(port=PORT, protocol=PROTOCOL, ip=ip)

        self.loop.run_until_complete(_start_pubbing(num_msgs))

    def start_subbing(self, vk):
        self.sock = self.manager.create_socket(zmq.SUB)
        self.log.socket("connecting sub socket")
        self.sock.setsockopt(zmq.SUBSCRIBE, b'')
        self.sock.connect(port=PORT, protocol=PROTOCOL, vk=vk)

        sub_coro = self.sock.add_handler(handler_func=self.handle_pub)

        self.loop.run_until_complete(sub_coro)

    def handle_pub(self, frames):
        self.log.important("got pub msg with frames {}".format(frames))