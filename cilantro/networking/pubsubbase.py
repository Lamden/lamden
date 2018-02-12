import asyncio
import uvloop
import zmq
from zmq.asyncio import Context
# from aiohttp import web
from cilantro.serialization import JSONSerializer
from cilantro.proofs.pow import SHA3POW # Needed for Witness
from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS

# Using UV Loop for EventLoop, instead aysncio's event loop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class PubSubBase(object):
    def __init__(self, host=None, sub_port=None, pub_port=None, serializer=None):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = pub_port
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)
        self.serializer = serializer

        self.ctx = Context() # same as context variable
        # self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
        # self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)

        self.sub_socket = None
        self.pub_socket = None
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
            self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
            self.sub_socket.bind(self.sub_url)
            print('start subscribing to url: ' + self.sub_url)
            self.sub_socket.subscribe(b'') # as of 17.0
            # self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')  # no filters applied
        except Exception as e:
            return {'status': 'Could not send '}
        while True:
            req = await self.sub_socket.recv()
            # req = await self.sub_socket.recv_json()
            self.handle_req(req)

    async def handle_req(self, data=None):
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


    def publish_req(self, data=None):
        # SERIALIZE Function
        # When you need to serialize.
        # data = self.serialize(data)
        try:
            self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)
            self.pub_socket.connect(self.pub_url)
            self.serializer.send(data, self.pub_socket)
        except Exception as e:
            return {'status': 'Could not send transaction'}
        finally:
            self.pub_socket.close() # stop listening to sub_url

class Witness(PubSubBase):
    def __init__(self, host='127.0.0.1', sub_port='9999', serializer=JSONSerializer, hasher=SHA3POW):
        PubSubBase.__init__(self, host=host, sub_port=sub_port, serializer=serializer)
        self.hasher = hasher
        self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
        self.pub_socket = None # Don't really need this... Just here as a reference

    async def handle_req(self, data=None):
        """
        async def accept_incoming_transactions(self): after the while loop
        :param data:
        :return:
        """
        try:
            raw_tx = self.serializer.deserialize(data)
        except Exception as e:
            return{'status': 'Could not deserialize transaction'}

        if self.hasher.check(raw_tx, raw_tx.payload['metadata']['proof']):
            self.confirmed_transaction_routine()
        else:
            return {'status': 'Could not confirm transaction POW'}

    def activate_witness_publisher(self):
        self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)
        self.pub_socket.bind(self.pub_url)

    async def confirmed_transaction_routine(self, raw_tx):
        tx_to_delegate = self.serializer.serialize(raw_tx)
        self.activate_witness_publisher()
        await self.pub_socket.send(tx_to_delegate)
        self.pub_socket.unbind(self.pub_url)  # unbind socket?

class Masternode(PubSubBase):
    def __init__(self, host='*', internal_port='9999', external_port='8080', serializer=JSONSerializer):
        PubSubBase.__init__(self, host=host, sub_port=internal_port, pub_port=external_port, serializer=serializer)

    def __validate_transaction_length(self, data: bytes):
        if not data:
            return False
        elif len(data) >= MAX_REQUEST_LENGTH:
            return False
        else:
            return True

    def __validate_transaction_fields(self, data: dict):
        if not data:
            return False
        elif 'to' not in data['payload']:
            return False
        elif 'amount' not in data['payload']:
            return False
        elif 'from' not in data['payload']:
            return False
        else:
            return True



if __name__ == '__main__':
    # Subscribe
    print("a")
    sub = PubSubBase(sub_port='7777', pub_port='8888')
    print("b")
    # sub.start_async()
