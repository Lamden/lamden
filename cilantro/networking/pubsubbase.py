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

        self.ctx = Context.instance() # same as context variable
        self.context = zmq.Context() # same as above
        self.witness_sub = self.ctx.socket(socket_type=zmq.SUB)
        self.witness_pub = self.context.socket(socket_type=zmq.PUB)
        self.loop = None


    def start_async(self):
        try:
            self.loop = asyncio.get_event_loop()  # add uvloop here
            # self.loop.create_task(...)
        except Exception as e:
            print(e)
        finally:
            self.loop.stop()

    async def handle_req(self):
        """
        Listen
        # should override
        :return:
        """
        try:
            self.witness_sub.bind(self.sub_url)
            self.witness_sub.setsockopt(zmq.SUBSCRIBE, '')  # no filters applied
        except Exception as e:
            return {'status': 'Could not send transaction'}
        finally:
            self.witness_sub.unbind(self.sub_url)
        while True:
            req = await self.witness_sub.recv()
            # Handle request at the bottom



    async def publish_req(self, data=None):
        d = None
        # 1) Serialize data/requests
        try:
            d = self.serializer.serialize(data)
        except:
            return {'status': 'Could not serialize data'}
        # 2) Send data/request
        try:
            """
            Bind the socket to an address.
            This causes the socket to listen on a network port. 
            Sockets on the other side of this connection will use Socket.connect(addr) to connect to this socket.
            """
            self.witness_pub.bind(self.sub_url) # Listen to sub_url
            self.serializer.send(d, self.witness_pub)
        except Exception as e:
            return {'status': 'Could not send transaction'}
        finally:
            self.witness_pub.unbind(self.sub_url) # stop listening to sub_url




if __name__ == '__main__':
    # a = Witness()
    # a.start_async()
    # a = zmq.Context()
    # pub = a.socket(zmq.PUB)
    # ctx = Context.instance()
    # sub = ctx.socket(socket_type=zmq.SUB)

    my_obj = PubSubBase()
    print("a")

