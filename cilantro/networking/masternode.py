import uvloop
from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS, NTP_URL
from cilantro.transactions.testnet import TestNetTransaction
from cilantro.networking import BaseNode
from aiohttp import web
from cilantro.serialization import JSONSerializer
from cilantro.db.masternode.blockchain_driver import BlockchainDriver
import sys
import ntplib
import uuid
web.asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


'''
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.
    
    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving. 
'''

class Masternode(BaseNode):
    def __init__(self, base_url='127.0.0.1', internal_port='9999', external_port='8080', serializer=JSONSerializer):
        BaseNode.__init__(self, base_url=base_url, publisher_port=internal_port, serializer=serializer)
        self.external_port = external_port
        # self.time_client = ntplib.NTPClient()  TODO -- investigate why we can't query NTP_URL with high frequency
        self.db = BlockchainDriver(serializer=serializer)

        # FOR TESTNET ONLY
        # self.db.create_genesis()

    def process_transaction(self, data: bytes):
        """
        Validates the POST Request from Client, and publishes it to Witnesses
        :param data: binary encoded JSON data from the user's POST request
        :return: A dictionary indicating the status of Masternode's attempt to publish the request to witnesses
        """
        # 1) Validate transaction size
        if not self.__validate_transaction_length(data):
            return {'error': TX_STATUS['INVALID_TX_SIZE']}
        # 2) De-serialize data
        try:
            d = self.serializer.deserialize(data)
        except Exception as e:
            print("in Exception of process_transaction")
            return {'error': TX_STATUS['SERIALIZE_FAILED'].format(e)}
        # Validate transaction fields
        try:
            TestNetTransaction.validate_tx_fields(d)
        except Exception as e:
            print(e)
            return {'error': TX_STATUS['INVALID_TX_FIELDS'].format(e)}

        # Add timestamp and UUID
        # d['metadata']['timestamp'] = self.time_client.request(NTP_URL, version=3).tx_time
        d['metadata']['uuid'] = str(uuid.uuid4())

        return self.handle_request(d)

    def handle_request(self, request):
        # serialize
        # put on queue
        self.queue.put(request)

    def process_local_queue(self, msg):
        try:
            self.message_queue.pub_socket.send_json(msg)
        except Exception as e:
            print("error publishing request: {}".format(e))
            return {'status': 'Could not publish request'}

        print("Successfully published request: {}".format(msg))
        return {'status': 'Successfully published request: {}'.format(msg)}

    def add_block(self, data: bytes):
        print("process block got raw data: {}".format(data))
        d = None
        try:
            d = self.serializer.deserialize(data)
            # TODO -- validate block
        except Exception as e:
            print("Error deserializing block: {}".format(e))
            return {'error_status': 'Could not deserialize block -- Error: {}'.format(e)}

        try:
            print("persisting block...")
            self.db.persist_block(d)
            print("finished persisting block")
        except Exception as e:
            print("Error persisting block: {}".format(e))
            return {'error_status': 'Could not persist block -- Error: {}'.format(e)}

        print("Successfully stored block data: {}".format(d))
        return {'status': "persisted block with data:\n{}".format(d)}

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

    async def process_block_request(self, request):
        r = self.add_block(data=await request.content.read())
        return web.Response(text=str(r))

    def setup_web_server(self):
        app = web.Application()
        app.router.add_post('/', self.process_request)
        app.router.add_post('/add_block', self.process_block_request)
        web.run_app(app, host=self.host, port=int(self.external_port))
