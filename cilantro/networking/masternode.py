from cilantro.networking.constants import MAX_REQUEST_LENGTH
from cilantro.serialization import JSONSerializer

from aiohttp import web
import zmq

import sys
if sys.platform != 'win32':
    import uvloop
    web.asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
else:
    web.asyncio.set_event_loop_policy(None)

'''
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.
    
    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving. 
'''

class Masternode(object):
    def __init__(self, host='127.0.0.1', internal_port='9999', external_port='8080', serializer=JSONSerializer):
        self.host = host
        self.internal_port = internal_port
        self.external_port = external_port
        self.serializer = serializer

        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)

        self.url = 'tcp://{}:{}'.format(self.host, self.internal_port)

    def process_transaction(self, data=None):
        if not self.validate_transaction(data):
            return {'status': 'invalid transaction'}

        d = None
        try:
            d = self.serializer.serialize(data)
        except:
            return {'status': 'Could not serialize transaction' }

        try:
            self.publisher.bind(self.url)
            self.serializer.send(d, self.publisher)
        except Exception as e:
            return {'status': 'Could not send transaction'}
        finally:
            self.publisher.unbind(self.url)

        return { 'status' : '{} successfully published to the network'.format(d) }

    def validate_transaction(self, data=None):
        """
        Validation function for the payload of the request. Validates against payload size,
        as well as valid payload fields for basic transaction

        :input: data extracted from the Transaction's POST payload
        :return: A boolean if the payload is transaction or not
        """
        if not data:
            return False
        elif data.content_length <= MAX_REQUEST_LENGTH:
            return False
        elif 'to' not in data['payload']:
            return False
        elif 'amount' not in data['payload']:
            return False
        elif 'from' not in data['payload']:
            return False

        return True

    async def process_request(self, request):
        r = self.process_transaction(await request.content.read())
        return web.Response(text=str(r))

    async def setup_web_server(self):
        app = web.Application()
        app.router.add_post('/', self.process_transaction)
        web.run_app(app, host=self.host, port=int(self.external_port))

