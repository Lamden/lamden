import uvloop
from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS, NTP_URL
from cilantro.transactions.testnet import TestNetTransaction
from aiohttp import web
import ntplib
import sys
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

        self.ntp_client = ntplib.NTPClient()

        self.url = 'tcp://{}:{}'.format(self.host, self.internal_port)

    def process_transaction(self, data=None):
        # Validate transaction size
        if not self.__validate_transaction_length(data):
            return {'error': TX_STATUS['INVALID_TX_SIZE']}

        d = None
        try:
            d = self.serializer.serialize(data)
        except:
            return {'error': TX_STATUS['SERIALIZE_FAILED']}

        # Validate transaction fields
        try:
            TestNetTransaction.validate_tx_fields(d)
        except Exception as e:
            print(e)
            return {'error': TX_STATUS['INVALID_TX_FIELDS'].format(e)}

        # Add timestamp to metadata
        time_stamp = self.ntp_client.request(NTP_URL, version=3).tx_time
        d['metadata']['timestamp'] = str(time_stamp)

        print(d)

        try:
            self.publisher.bind(self.url)
            self.serializer.send(d, self.publisher)
        except Exception as e:
            print("error binding socket: ", str(e))
            return {'error': TX_STATUS['SEND_FAILED']}
        finally:
            self.publisher.close()
            self.context.destroy()

        return {'success': TX_STATUS['SUCCESS'].format(d)}

    def __validate_transaction_length(self, data: bytes):
        if not data:
            return False
        elif sys.getsizeof(data) >= MAX_REQUEST_LENGTH:
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

