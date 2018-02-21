import asyncio

import zmq
from zmq.asyncio import Context
from concurrent.futures import ThreadPoolExecutor
import sys

from threading import Thread

# Using UV Loop for EventLoop, instead aysncio's event loop
if sys.platform != 'win32':
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class BaseNode(object):
    def __init__(self, host=None, sub_port=None, pub_port=None, serializer=None):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = pub_port
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)
        self.serializer = serializer

        self.ctx = None
        self.sub_socket = None
        self.pub_socket = None
        self.loop = None

        self.thread = None

    def start_listening(self):
        try:
            loop = asyncio.new_event_loop()
            self.thread = Thread(target=self.start_subscribing, args=(loop,))
            self.thread.start()
        except Exception as e:
            print(e)

    def start_subscribing(self, loop):
        asyncio.set_event_loop(loop)
        self.ctx = zmq.Context()
        self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
        self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.pub_url)

        self.sub_socket.bind(self.sub_url)
        self.sub_socket.subscribe(b'')

        while True:
            req = self.sub_socket.recv()
            asyncio.ensure_future(self.handle_req(req))

    async def handle_req(self, data: bytes):
        """
        Callback that is executed when the node receives data from its subscriber port. This should be
        overridden by child classes
        :param data: Binary data received from node's subscribe socket
        :return: A dictionary indicating the status of the handle request
        """
        raise NotImplementedError

    def publish_req(self, data: dict):
        """
        Function to publish data to pub_socket (pub_socket is connected during initialization)
        TODO -- add support for publishing with filters

        :param data: A python dictionary signifying the data to publish
        :return: A dictionary indicating the status of the publish attempt
        """
        try:
            self.pub_socket.send_json(data)
        except Exception as e:
            print("error publishing request: {}".format(e))
            return {'status': 'Could not publish request'}

        print("Successfully published request: {}".format(data))
        return {'status': 'Successfully published request: {}'.format(data)}

    def disconnect(self):
        try:
            self.ctx.destroy()
            self.thread.stop()
        except:
            pass