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

# IMPORTS FOR DEMO
import json
import time
import os
from cilantro.networking.constants import FAUCET_PERCENT
from cilantro.wallets.ed25519 import ED25519Wallet
from cilantro.proofs.pow import SHA3POW
# END DEMO IMPORT


web.asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


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
        self.external_port = external_port
        # self.time_client = ntplib.NTPClient()  TODO -- investigate why we can't query NTP_URL with high frequency
        self.db = BlockchainDriver(serializer=serializer)

        # FOR TESTNET ONLY
        self.db.create_genesis()
        self.updates = None
        file_path = os.getcwd() + '/cilantro/faucet.json'
        # faucet_json = json.load(open(file_path))
        # self.faucet_s = faucet_json['signing_key']
        # self.faucet_v = faucet_json['verifying_key']

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
        d['metadata']['timestamp'] = time.time()  # INSECURE, FOR DEMO ONLY
        d['metadata']['uuid'] = str(uuid.uuid4())

        return self.publish_req(d)

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
            self.updates = self.db.persist_block(d)
            print("finished persisting block")
        except Exception as e:
            print("Error persisting block: {}".format(e))
            return {'error_status': 'Could not persist block -- Error: {}'.format(e)}

        print("Successfully stored block data: {}".format(d))
        # return {'status': "persisted block with data:\n{}".format(d)}

        print("BLOCK PERSIST UPDATES: {}".format(self.updates))

    def faucet(self, data: bytes):
        """
        -- FOR TEST NET ONLY --
        Sends some money from the faucet to the users wallet
        :param data: The wallet id to credit (as binary data)
        """
        d = None
        try:
            d = self.serializer.deserialize(data)
        except Exception as e:
            print("Error deserializing faucet request: {}".format(data))
            return {'error_status': "Error deserializing faucet request: {}".format(data)}

        if 'wallet_key' not in d:
            print("Error! wallet_key not in faucet request")
            return {'error status': 'wallet_key not in faucet request!'}

        wallet_key = d['wallet_key']
        # Check if user has already used faucet
        if self.db.check_faucet_used(wallet_key):
            print("Uh oh. Wallet {} already used the faucet.".format(wallet_key))
            return {'error_status': 'user already used faucet'}
        else:
            print("First faucuet use for wallet {}".format(wallet_key))
            self.db.add_faucet_use(wallet_key)

        # Create signed standard transaction from faucet
        amount = self.db.get_balance(self.faucet_v)[self.faucet_v] * FAUCET_PERCENT
        tx = {"payload": {"to": wallet_key, "amount": str(amount), "from": self.faucet_v, "type": "t"},
              "metadata": {}}
        tx["metadata"]["proof"] = SHA3POW.find(self.serializer.serialize(tx["payload"]))[0]
        tx["metadata"]["signature"] = ED25519Wallet.sign(self.faucet_s, self.serializer.serialize(tx["payload"]))

        return self.process_transaction(self.serializer.serialize(tx))

    def get_balance(self, request):
        wallet_key = request.match_info['wallet_key']
        if wallet_key == 'all':
            return web.json_response(self.db.get_all_balances())
        else:
            return web.json_response(self.db.get_balance(wallet_key))

    def get_updates(self, request):
        if self.updates is None:
            return web.json_response({})
        else:
            return web.json_response(self.updates)

    def __validate_transaction_length(self, data: bytes):
        if not data:
            return False
        elif sys.getsizeof(data) >= MAX_REQUEST_LENGTH:
            return False
        else:
            return True

    def get_blockchain_json(self, data: bytes):
        return self.db.get_blockchain_data()

    async def process_request(self, request):
        r = self.process_transaction(data=await request.content.read())
        return web.Response(text=str(r))

    async def process_block_request(self, request):
        r = self.add_block(data=await request.content.read())
        return web.Response(text=str(r))

    async def process_faucet_request(self, request):
        r = self.faucet(data=await request.content.read())
        return web.Response(text=str(r))

    async def process_blockchain_request(self, request):
        d = self.get_blockchain_json(data=await request.content.read())
        return web.json_response(d)


    def setup_web_server(self):
        app = web.Application()
        app.router.add_post('/', self.process_request)
        app.router.add_post('/add_block', self.process_block_request)
        app.router.add_post('/faucet', self.process_faucet_request)
        app.router.add_get('/updates', self.get_updates)
        app.router.add_get('/blockchain', self.process_blockchain_request)

        resource = app.router.add_resource('/balance/{wallet_key}')
        resource.add_route('GET', self.get_balance)

        web.run_app(app, host=self.host, port=int(self.external_port))
