from cilantro.logger.base import get_logger
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.base.base import MessageBase
from cilantro.protocol import wallet

from cilantro.protocol.reactor.socket_manager import SocketManager
from cilantro.protocol.reactor.lsocket import LSocket
from cilantro.protocol.overlay.ironhouse import Ironhouse
from cilantro.protocol.multiprocessing.worker import Worker

import os
import asyncio
import zmq.asyncio
import time


PORT = 9432
PORT_INSECURE = 9433
PROTOCOL = 'tcp'

PUB_SOCK_KEY = 'default_pub'
SUB_SOCK_KEY = 'default_sub'
DEFAULT_DOMAIN = 'wonderland'


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


class PubSubAuthTester(Worker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dict of socket key -> LSocket instance
        self.pub_sockets = {}
        self.sub_sockets = {}

    def start(self):
        self.loop.run_forever()

    def add_pub_socket(self, ip, port=PORT, protocol=PROTOCOL, secure=False, domain=DEFAULT_DOMAIN, key=PUB_SOCK_KEY):
        assert key not in self.pub_sockets, "Key {} already exists in pub sockets {}".format(key, self.pub_sockets)

        # sock = self.manager.create_socket(zmq.PUB, secure=secure, domain=domain)
        sock = self.manager.create_socket(zmq.PUB)
        sock.bind(port=PORT, protocol=protocol, ip=ip)

        self.log.socket("Binding pub socket with key {} using ip {}".format(key, ip))
        self.pub_sockets[key] = sock

    def add_sub_socket(self, filter=b'', secure=False, domain=DEFAULT_DOMAIN, key=SUB_SOCK_KEY):
        assert key not in self.sub_sockets, "Key {} already exists in sub sockets {}".format(key, self.sub_sockets)
        assert type(filter) is bytes, "Filter must be bytes, not {}".format(filter)

        # sock = self.manager.create_socket(zmq.SUB, secure=secure, domain=domain)
        sock = self.manager.create_socket(zmq.SUB)
        sock.setsockopt(zmq.SUBSCRIBE, filter)
        sock.add_handler(handler_func=self.handle_sub, start_listening=True)

        self.sub_sockets[key] = sock

    def connect_sub(self, key=SUB_SOCK_KEY, vk='', ip='', port=PORT, protocol=PROTOCOL):
        assert key in self.sub_sockets, "Key {} not found in sub sockets {}".format(key, self.sub_sockets)

        sock = self.sub_sockets[key]
        sock.connect(port=port, protocol=protocol, vk=vk, ip=ip)

    def start_publishing(self, num_msgs=50, interval=1):
        assert len(self.pub_sockets) > 0, "Must add at least 1 pub socket to start publishing"

        async def _start_pubbing(num):
            for i in range(num):
                self.log.info("sending pub {}".format(i))
                msg = [b'', 'hello #{} from {}'.format(i, os.getenv('HOST_IP')).encode()]
                for sock in self.pub_sockets.values():
                    sock.send_multipart(msg)
                await asyncio.sleep(interval)

        asyncio.ensure_future(_start_pubbing(num_msgs))


    def handle_sub(self, frames):
        self.log.important("got <secure> pub msg with frames {}".format(frames))

    def handle_sub_insecure(self, frames):
        self.log.important("got <insecure> pub msg with frames {}".format(frames))