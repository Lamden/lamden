import asyncio
import uvloop
import zmq
from zmq.asyncio import Context

# Using UV Loop for EventLoop, instead aysncio's event loop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class BaseNode(object):
    def __init__(self, host=None, sub_port=None, pub_port=None, serializer=None):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = pub_port
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)
        self.serializer = serializer

        self.ctx = Context()
        self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
        self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.pub_url)

        self.loop = None

    def start_async(self):
        try:
            self.loop = asyncio.get_event_loop()
            self.loop.run_until_complete(self.start_subscribing())
        except Exception as e:
            print("Error starting subscriber event loop: {}".format(e))

    async def start_subscribing(self):
        """
        Start subscribing to requests on self.pub_socket (currently with no filters)
        TODO -- add support for subscribing with filters
        :return: A dictionary indicating the status of the publish attempt
        """
        try:
            self.sub_socket.bind(self.sub_url)
            self.sub_socket.subscribe(b'')
        except Exception as e:
            print("Error subscribing to socket {}, error: {}".format(self.sub_url, e))
            return {'status': 'Could not open/bind sub_socket'}

        while True:
            print("Subscriber waiting for data...")
            req = await self.sub_socket.recv()
            print('Subscriber received data: ', req)
            await self.handle_req(req)

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
        self.ctx.destroy()