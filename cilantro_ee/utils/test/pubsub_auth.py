from cilantro_ee.core.utils.worker import Worker

import os
import asyncio
import zmq.asyncio
import time


PORT = 9432
PORT_INSECURE = 9433
PROTOCOL = 'tcp'

PUB_SOCK_KEY = 'default_pub'
SUB_SOCK_KEY = 'default_sub'
DEFAULT_DOMAIN = '*'


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


class PubSubAuthTester(Worker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log.important3("PubSubAuthTester starting with VK {}".format(self.verifying_key))

        # Dict of socket key -> LSocket instance
        self.pub_sockets = {}
        self.sub_sockets = {}

    def start(self):
        self.loop.run_forever()

    def add_pub_socket(self, ip, port=PORT, protocol=PROTOCOL, secure=False, domain=DEFAULT_DOMAIN, socket_key=PUB_SOCK_KEY):
        assert socket_key not in self.pub_sockets, "Key {} already exists in pub sockets {}".format(socket_key, self.pub_sockets)

        sock = self.manager.create_socket(zmq.PUB, secure=secure, domain=domain)
        self.log.socket("Binding pub socket with key {} using ip {}".format(socket_key, ip))
        sock.bind(port=PORT, protocol=protocol, ip=ip)

        self.pub_sockets[socket_key] = sock

    def add_sub_socket(self, filter=b'', secure=False, domain=DEFAULT_DOMAIN, socket_key=SUB_SOCK_KEY):
        assert socket_key not in self.sub_sockets, "Key {} already exists in sub sockets {}".format(socket_key, self.sub_sockets)
        assert type(filter) is bytes, "Filter must be bytes, not {}".format(filter)

        sock = self.manager.create_socket(zmq.SUB, secure=secure, domain=domain)
        sock.setsockopt(zmq.SUBSCRIBE, filter)
        sock.add_handler(handler_func=self.handle_sub, start_listening=True)

        self.sub_sockets[socket_key] = sock

    def connect_sub(self, socket_key=SUB_SOCK_KEY, vk='', ip='', port=PORT, protocol=PROTOCOL):
        assert socket_key in self.sub_sockets, "Key {} not found in sub sockets {}".format(socket_key, self.sub_sockets)

        self.log.important("connecting to vk {}".format(vk))

        sock = self.sub_sockets[socket_key]
        sock.connect(port=port, protocol=protocol, vk=vk, ip=ip)
        time.sleep(2) # TODO for davis

    def start_publishing(self, num_msgs=50, interval=1, filter=b''):
        assert len(self.pub_sockets) > 0, "Must add at least 1 pub socket to start publishing"
        async def _start_pubbing(num):
            for i in range(num):
                self.log.info("sending pub {}".format(i))
                msg = [filter, 'hello #{} from {}'.format(i, os.getenv('HOST_IP')).encode()]
                for sock in self.pub_sockets.values():
                    sock.send_multipart(msg)
                await asyncio.sleep(interval)

        asyncio.ensure_future(_start_pubbing(num_msgs))

    def send_pub(self, msg: bytes, filter: bytes=b'', socket_key=PUB_SOCK_KEY):
        assert socket_key in self.pub_sockets, "Key {} not found in pub sockets {}".format(socket_key, self.pub_sockets)
        assert type(msg) is bytes, "Msg arg must be bytes, not {}".format(msg)

        self.log.debugv("Sending msg {} with filter {} on socket with key {}".format(msg, filter, socket_key))
        self.pub_sockets[socket_key].send_multipart([filter, msg])

    def handle_sub(self, frames):
        self.log.important("got <secure> pub msg with frames {}".format(frames))
