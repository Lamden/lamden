import asyncio
import uvloop
import zmq
from zmq.asyncio import Context
import json

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

        self.ctx = Context() # same as context variable
        self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
        self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)
        self.pub_socket.connect(self.pub_url)

        self.loop = None

    def start_async(self):
        try:
            self.loop = asyncio.get_event_loop()  # add uvloop here
            self.loop.run_until_complete(self.start_subscribing())
        except Exception as e:
            print(e)
        finally:
            print("Loop finished")

    async def start_subscribing(self):
        """
        Listen
        :return:
        """
        try:
            self.sub_socket.bind(self.sub_url)
            self.sub_socket.subscribe(b'') # as of 17.0  - no filters applied
        except Exception as e:
            print(e)
            return {'status': 'Could not send '}
        while True:
            print("in the while loop")
            req = await self.sub_socket.recv()
            print('received', req)
            await self.handle_req(req)

    async def handle_req(self, data: bytes):
        """
        override
        :param data:
        :return:
        """
        pass

    def serialize(self, data):
        """
        Since the base class takes in a serializer
        :param data:
        :return:
        """
        try:
            d = self.serializer.serialize(data)
        except:
            return {'status': 'Could not serialize data'}
        return d


    def publish_req(self, data: bytes):
        """
        Function to publish data to pub_socket
        pub_socket is connected during initialization
        :param data:
        :return:
        """
        try:
            print("in publish request")
            d = json.loads(data.decode())
            self.pub_socket.send_json(d)
        except Exception as e:
            print("in publish_req Exception:")
            print(e)
            return {'status': 'Could not publish request'}
        return {'status': 'Successfully published request'}