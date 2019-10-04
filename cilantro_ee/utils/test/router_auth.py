from cilantro_ee.core.utils.worker import Worker
from cilantro_ee.messages.base.base import MessageBase

import os
import asyncio
import zmq.asyncio


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


class RouterAuthTester(Worker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.router = None

    def start(self):
        self.loop.run_forever()

    def create_router_socket(self, identity: bytes, secure=True, domain=DEFAULT_DOMAIN, name='Router', debug=True):
        self.router = self.manager.create_socket(zmq.ROUTER, secure=secure, domain=domain, name=name)
        self.router.setsockopt(zmq.IDENTITY, identity)
        self.router.add_handler(handler_func=self.handle_router_msg, start_listening=True)
        if debug:
            self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)

    def connect_router_socket(self, vk='', ip='', port=PORT, protocol=PROTOCOL):
        assert self.router, "create_router_socket must be called first"
        self.router.connect(ip=ip, vk=vk, port=port, protocol=protocol)

    def bind_router_socket(self, ip, port=PORT, protocol=PROTOCOL):
        assert self.router, "create_router_socket must be called first"
        self.router.bind(ip=ip, port=port, protocol=protocol)

    def send_raw_msg(self, id_frame: bytes, msg: bytes):
        self.router.send_multipart([id_frame, msg])

    def send_msg(self, msg: MessageBase, header: bytes):
        self.router.send_msg(msg, header)

    def handle_router_msg(self, frames):
        self.log.important("Router got msg with frames {}".format(frames))
