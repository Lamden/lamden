import uvloop
from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS
from cilantro.transactions.testnet import TestNetTransaction
from cilantro.networking import BaseNode
from aiohttp import web
import sys
web.asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from cilantro.serialization import JSONSerializer
import json

'''
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.
    
    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving. 
'''
class Masternode(BaseNode):
    def __init__(self, host='127.0.0.1', internal_port='9999', external_port='8080', serializer=JSONSerializer):
        BaseNode.__init__(self, host=host, pub_port=internal_port, serializer=serializer)
        self.external_port = external_port  # port to run server
        # Debugger
        self.counter = 0

    def process_transaction(self, data: bytes):
        """
        Validates the POST Request from Client
        :param data:
        :return:
        """
        # Validate transaction size
        if not self.__validate_transaction_length(data):
            return {'error': TX_STATUS['INVALID_TX_SIZE']}
        # De-serialize data
        try:
            d = json.loads(data.decode())
        except Exception as e:
            print("in Exception of process_transaction")
            return {'error': TX_STATUS['SERIALIZE_FAILED'].format(e)}
        # Validate transaction fields
        try:
            TestNetTransaction.validate_tx_fields(d)
        except Exception as e:
            print(e)
            return {'error': TX_STATUS['INVALID_TX_FIELDS'].format(e)}
        # Debugger
        self.counter+=1
        print(self.counter)
        return self.publish_req(data)

    def __validate_transaction_length(self, data: bytes):
        if not data: #if data is None
            return False
        elif len(data) >= MAX_REQUEST_LENGTH:
            return False
        else:
            return True

    async def process_request(self, request):
        print(request.content.read())
        r = self.process_transaction(data=await request.content.read())
        return web.Response(text=str(r))

    def setup_web_server(self):
        app = web.Application()
        app.router.add_post('/', self.process_request)
        web.run_app(app, host=self.host, port=int(self.external_port))