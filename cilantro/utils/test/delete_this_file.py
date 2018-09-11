from cilantro.logger.base import get_logger
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.base.base import MessageBase
from cilantro.protocol import wallet

from cilantro.protocol.reactor.socket_manager import SocketManager
from cilantro.protocol.reactor.lsocket import LSocket
from cilantro.protocol.overlay.ironhouse import Ironhouse

import os
import asyncio
import zmq.asyncio
import time


PORT = 9432
PORT_INSECURE = 9433
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
                msg = [b'', 'hello #{} from {}'.format(i, os.getenv('HOST_IP')).encode()]
                self.sock.send_multipart(msg)
                self.sock_insecure.send_multipart(msg)
                await asyncio.sleep(1)

        self.log.socket("binding pub socket")

        self.sock = self.manager.create_socket(zmq.PUB, secure=True, domain='wonderland')
        self.sock.bind(port=PORT, protocol=PROTOCOL, ip=ip)

        self.sock_insecure = self.manager.create_socket(zmq.PUB)
        self.sock_insecure.bind(port=PORT_INSECURE, protocol=PROTOCOL, ip=ip)

        self.loop.run_until_complete(_start_pubbing(num_msgs))

    def start_subbing(self, vk):
        if not self.sock:
            self.sock = self.manager.create_socket(zmq.SUB, secure=True, domain='wonderland')
            self.sock.setsockopt(zmq.SUBSCRIBE, b'')
            self.sock_insecure = self.manager.create_socket(zmq.SUB)
            self.sock_insecure.setsockopt(zmq.SUBSCRIBE, b'')
        self.sock.add_handler(handler_func=self.handle_pub, start_listening=True)
        self.sock_insecure.add_handler(handler_func=self.handle_sub_insecure, start_listening=True)
        self.log.socket("connecting sub socket")
        self.sock.connect(port=PORT, protocol=PROTOCOL, vk=vk)
        self.sock_insecure.connect(port=PORT_INSECURE, protocol=PROTOCOL, vk=vk)

    def handle_pub(self, frames):
        self.log.important("got <secure> pub msg with frames {}".format(frames))

    def handle_sub_insecure(self, frames):
        self.log.important("got <insecure> pub msg with frames {}".format(frames))
