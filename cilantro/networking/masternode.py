import uvloop
from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS
from aiohttp import web
web.asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from cilantro.serialization import JSONSerializer
import zmq

'''
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.
    
    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving. 
'''

class Masternode(object):
    def __init__(self, host='*', internal_port='9999', external_port='8080', serializer=JSONSerializer):
        self.host = host
        self.internal_port = internal_port # port to publish request
        self.external_port = external_port # port to run server
        self.serializer = serializer

        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)

        self.url = 'tcp://{}:{}'.format(self.host, self.internal_port)

    def process_transaction(self, data=None):
        if not self.__validate_transaction_length(data):
            return TX_STATUS['INVALID_TX_SIZE']

        d = None
        try:
            d = self.serializer.serialize(data)
        except:
            return TX_STATUS['SERIALIZE_FAILED']

        if not self.__validate_transaction_fields(d):
            return TX_STATUS['INVALID_TX_FIELDS']

        try:
            self.publisher.bind(self.url)
            self.serializer.send(d, self.publisher)
        except Exception as e:
            print("error binding socket: ", str(e))
            return TX_STATUS['SEND_FAILED']
        finally:
            self.publisher.close()
            self.context.destroy()

        return TX_STATUS['SUCCESS']['status'].format(d)

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

    async def process_request(self, request):
        r = self.process_transaction(data=await request.content.read())
        return web.Response(text=str(r))

    async def setup_web_server(self):
        app = web.Application()
        app.router.add_post('/', self.process_request)
        web.run_app(app, host=self.host, port=int(self.external_port))

