import asyncio
import uvloop
import zmq
from zmq.asyncio import Context
# from aiohttp import web
from cilantro.serialization import JSONSerializer

# Using UV Loop for EventLoop, instead aysncio's event loop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class PubSubBase(object):
    def __init__(self, host='127.0.0.1', sub_port='9999', pub_port='7777', serializer = JSONSerializer):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = pub_port
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)
        self.serializer = serializer

        self.ctx = Context() # same as context variable
        self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
        self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)
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
            print('start subscribing to url: ' + self.sub_url)
            self.sub_socket.subscribe(b'') # as of 17.0
            # self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')  # no filters applied
        except Exception as e:
            return {'status': 'Could not send '}
        while True:
            req = await self.sub_socket.recv()
            # req = await self.sub_socket.recv_json()
            # self.handle_req(req)



    async def handle_req(self, data=None):
        """
        override
        :param data:
        :return:
        """
        raise NotImplementedError


    def publish_req(self, data=None):
        # d = None
        # # 1) Serialize data/requests
        # try:
        #     d = self.serializer.serialize(data)
        # except:
        #     return {'status': 'Could not serialize data'}
        # # 2) Send data/request
        try:
            self.pub_socket.connect(self.pub_url)
            self.serializer.send(data, self.pub_socket)
        except Exception as e:
            return {'status': 'Could not send transaction'}
        finally:
            self.pub_socket.close() # stop listening to sub_url

if __name__ == '__main__':
    # Subscribe
    sub = PubSubBase(sub_port='7777', pub_port='8888')
    sub.start_async()
