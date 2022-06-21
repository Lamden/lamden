from sanic import Sanic
from sanic import response
from sanic.websocket import WebSocketProtocol
from lamden.logger.base import get_logger
import json as _json
from contracting.client import ContractingClient
from contracting.db.encoder import encode, decode
from contracting.db.driver import ContractDriver
from contracting.compilation import parser
from lamden import storage
from lamden.crypto.canonical import tx_hash_from_tx
from lamden.crypto.transaction import TransactionException
from lamden.crypto.wallet import Wallet

import decimal
from contracting.stdlib.bridge.decimal import ContractingDecimal
from lamden.nodes.base import FileQueue

import ssl
import asyncio
import socketio
import json

from lamden.crypto import transaction
import decimal

import datetime
# Instantiate the parser
import argparse

log = get_logger("MN-WebServer")

log = get_logger("MN-WebServer")

class NonceEncoder(_json.JSONEncoder):
    def default(self, o, *args, **kwargs):
        if isinstance(o, dict):
            return int(o.get('__fixed__'))

        if isinstance(o, ContractingDecimal):
            if int(o._d) == o._d:
                return int(o._d)
            else:
                return {
                    '__fixed__': str(o._d)
                }

        if isinstance(o, decimal.Decimal):
            if int(o) == o:
                return int(o)
            else:
                return float(o)

        return super().default(o, *args, **kwargs)


class WebServer:
    def __init__(self, contracting_client: ContractingClient, driver: ContractDriver, wallet,
                 blocks: storage.BlockStorage,
                 queue=FileQueue(),
                 port=8080, ssl_port=443, ssl_enabled=False,
                 ssl_cert_file='~/.ssh/server.csr',
                 ssl_key_file='~/.ssh/server.key',
                 workers=2, debug=True, access_log=False,
                 max_queue_len=10_000,
                 event_service_port=8000,
                 topics=[]):
        # Setup base Sanic class and CORS
        self.app = Sanic(__name__)
        self.app.config.update({
            'REQUEST_MAX_SIZE': 32_000,
            'REQUEST_TIMEOUT': 10,
            'KEEP_ALIVE': False,
        })
        self.cors = None

        # Initialize the backend data interfaces
        self.client = contracting_client
        self.driver = driver
        self.nonces = storage.NonceStorage()
        self.blocks = blocks

        self.static_headers = {}

        self.wallet = wallet
        self.queue = queue
        self.max_queue_len = max_queue_len

        self.port = port

        self.ssl_port = ssl_port
        self.ssl_enabled = ssl_enabled
        self.context = None

        # Create the SSL Context if needed
        if self.ssl_enabled:
            self.context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
            self.context.load_cert_chain(ssl_cert_file, keyfile=ssl_key_file)

        # Store other Sanic constants for when server starts
        self.workers = workers
        self.debug = debug
        self.access_log = access_log

        # Add Routes
        self.app.add_route(self.submit_transaction, '/', methods=['POST', 'OPTIONS'])
        self.app.add_route(self.ping, '/ping', methods=['GET', 'OPTIONS'])
        self.app.add_route(self.get_id, '/id', methods=['GET'])
        self.app.add_route(self.get_nonce, '/nonce/<vk>', methods=['GET'])

        # State Routes
        self.app.add_route(self.get_methods, '/contracts/<contract>/methods', methods=['GET'])
        self.app.add_route(self.get_variables, '/contracts/<contract>/variables')
        self.app.add_route(self.get_variable, '/contracts/<contract>/<variable>')
        self.app.add_route(self.get_contracts, '/contracts', methods=['GET'])
        self.app.add_route(self.get_contract, '/contracts/<contract>', methods=['GET'])
        self.app.add_route(self.get_constitution, '/constitution', methods=['GET'])
        # self.app.add_route(self.iterate_variable, '/contracts/<contract>/<variable>/iterate')

        # Latest Block Routes
        self.app.add_route(self.get_latest_block, '/latest_block', methods=['GET', 'OPTIONS', ])
        self.app.add_route(self.get_latest_block_number, '/latest_block_num', methods=['GET'])
        self.app.add_route(self.get_latest_block_hash, '/latest_block_hash', methods=['GET'])

        # General Block Route
        self.app.add_route(self.get_block, '/blocks', methods=['GET'])

        # TX Route
        self.app.add_route(self.get_tx, '/tx', methods=['GET'])

        self.coroutine = None

        self.topics = topics
        self.event_service_port = event_service_port
        self.sio = socketio.AsyncClient()

        self.__setup_sio_event_handlers()
        self.__register_app_listeners()

        self.ws_clients = set()
        self.app.add_websocket_route(self.ws_handler, '/')
    
    def __setup_sio_event_handlers(self):
        @self.sio.event
        async def connect():
            print("CONNECTED TO EVENT SERVER")
            for topic in self.topics:
                await self.sio.emit('join', {'room': topic})

        @self.sio.event
        async def disconnect():
            print("DISCONNECTED FROM EVENT SERVER")
            for topic in self.topics:
                await self.sio.emit('leave', {'room': topic})

        @self.sio.event
        async def event(data):
            for client in self.ws_clients:
                await client.send(encode(data))

    def __register_app_listeners(self):
        @self.app.listener('after_server_start')
        async def connect_to_event_service(app, loop):
            # TODO(nikita): what do we do in case event service is not running?
            try:
                await self.sio.connect(f'http://localhost:{self.event_service_port}')
                await self.sio.wait()
            except:
                pass

    async def ws_handler(self, request, ws):
        self.ws_clients.add(ws)

        try:
            self.driver.clear_pending_state()

            # send the connecting socket the latest block
            num = storage.get_latest_block_height(self.driver)
            block = self.blocks.get_block(int(num))

            eventData = {
                'event': 'latest_block',
                'data': block
            }

            await ws.send(encode(eventData))

            async for message in ws:
                pass
        finally:
            self.ws_clients.remove(ws)

    async def start(self):
        # Start server with SSL enabled or not
        if self.ssl_enabled:
            self.coroutine = asyncio.ensure_future(
                self.app.create_server(
                    host='0.0.0.0',
                    port=self.ssl_port,
                    debug=self.debug,
                    access_log=self.access_log,
                    ssl=self.context,
                    return_asyncio_server=True
                )
            )
        else:
            self.coroutine = asyncio.ensure_future(
                self.app.create_server(
                    host='0.0.0.0',
                    port=self.port,
                    debug=self.debug,
                    access_log=self.access_log,
                    return_asyncio_server=True
                )
            )

    # Main Endpoint to Submit TXs
    async def submit_transaction(self, request):
        log.debug(f'New request: {request}')

        if request.method == "OPTIONS":
            return response.text("",headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': "origin, content-type"
            })

        # Reject TX if the queue is too large
        if len(self.queue) >= self.max_queue_len:
            return response.json({'error': "Queue full. Resubmit shortly."}, status=503,
                                 headers={'Access-Control-Allow-Origin': '*'})

        tx_raw = _json.loads(request.body)
        log.error(tx_raw)
        # Check that the payload is valid JSON
        tx = decode(request.body)
        if tx is None:
            return response.json({'error': 'Malformed request body.'}, headers={'Access-Control-Allow-Origin': '*'})

        # Check that the TX is correctly formatted
        try:
            transaction.check_tx_formatting(tx, self.wallet.verifying_key)

            transaction.transaction_is_valid(
                transaction=tx,
                expected_processor=self.wallet.verifying_key,
                client=self.client,
                nonces=self.nonces
            )
            '''

            nonce, pending_nonce = transaction.get_nonces(
                sender=tx['payload']['sender'],
                processor=tx['payload']['processor'],
                driver=self.nonces
            )

            pending_nonce = transaction.get_new_pending_nonce(
                tx_nonce=tx['payload']['nonce'],
                nonce=nonce,
                pending_nonce=pending_nonce
            )

            self.nonces.set_pending_nonce(
                sender=tx['payload']['sender'],
                processor=tx['payload']['processor'],
                value=pending_nonce
            )
            '''

            self.nonces.set_nonce(
                sender=tx['transaction']['payload']['sender'],
                processor=tx['transaction']['payload']['processor'],
                value=tx['transaction']['payload']['nonce'] + 1
            )

        except TransactionException as e:
            log.error(f'Tx has error: {type(e)}')
            log.error(tx)
            return response.json(
                transaction.EXCEPTION_MAP[type(e)], headers={'Access-Control-Allow-Origin': '*'}
            )

        # Add TX to the processing queue
        self.queue.append(request.body)
        log.info('Added to q')

        # Return the TX hash to the user so they can track it
        tx_hash = tx_hash_from_tx(tx)

        return response.json({
            'success': 'Transaction successfully submitted to the network.',
            'hash': tx_hash
        }, headers={'Access-Control-Allow-Origin': '*'})

    # Network Status
    async def ping(self, request):
        return response.json({'status': 'online'}, headers={'Access-Control-Allow-Origin': '*'})

    # Get VK of this Masternode for Nonces
    async def get_id(self, request):
        return response.json({'verifying_key': self.wallet.verifying_key}, headers={'Access-Control-Allow-Origin': '*'})

    # Get the Nonce of a VK
    async def get_nonce(self, request, vk):
        latest_nonce = self.nonces.get_latest_nonce(sender=vk, processor=self.wallet.verifying_key)

        try:
            latest_nonce = int(latest_nonce)
        except:
            pass

        return response.json({
            'nonce': latest_nonce,
            'processor': self.wallet.verifying_key,
            'sender': vk
        }, headers={'Access-Control-Allow-Origin': '*'})

    # Get all Contracts in State (list of names)
    async def get_contracts(self, request):
        self.client.raw_driver.clear_pending_state()

        contracts = self.client.get_contracts()
        return response.json({'contracts': contracts}, headers={'Access-Control-Allow-Origin': '*'})

    # Get the source code of a specific contract
    async def get_contract(self, request, contract):
        self.client.raw_driver.clear_pending_state()

        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404,
                                 headers={'Access-Control-Allow-Origin': '*'})
        return response.json({'name': contract, 'code': contract_code}, status=200,
                             headers={'Access-Control-Allow-Origin': '*'})

    async def get_methods(self, request, contract):
        self.client.raw_driver.clear_pending_state()

        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404,
                                 headers={'Access-Control-Allow-Origin': '*'})

        funcs = parser.methods_for_contract(contract_code)

        return response.json({'methods': funcs}, status=200, headers={'Access-Control-Allow-Origin': '*'})

    async def get_variables(self, request, contract):
        self.client.raw_driver.clear_pending_state()

        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404,
                                 headers={'Access-Control-Allow-Origin': '*'})

        variables = parser.variables_for_contract(contract_code)

        return response.json(variables, headers={'Access-Control-Allow-Origin': '*'})

    async def get_variable(self, request, contract, variable):
        self.client.raw_driver.clear_pending_state()

        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404,
                                 headers={'Access-Control-Allow-Origin': '*'})

        key = request.args.get('key')
        if key is not None:
            key = key.split(',')

        k = self.client.raw_driver.make_key(contract=contract, variable=variable, args=key)
        value = self.client.raw_driver.get(k)

        if value is None:
            return response.json({'value': None}, status=404, headers={'Access-Control-Allow-Origin': '*'})
        else:
            return response.json({'value': value}, status=200, dumps=encode,
                                 headers={'Access-Control-Allow-Origin': '*'})

    # async def iterate_variable(self, request, contract, variable):
    #     contract_code = self.client.raw_driver.get_contract(contract)
    #
    #     if contract_code is None:
    #         return response.json({'error': '{} does not exist'.format(contract)}, status=404)
    #
    #     key = request.args.get('key')
    #     # if key is not None:
    #     #     key = key.split(',')
    #
    #     k = self.client.raw_driver.make_key(contract=contract, variable=variable, args=key)
    #
    #     values = self.client.raw_driver.driver.iter(k, length=500)
    #
    #     if len(values) == 0:
    #         return response.json({'values': None}, status=404)
    #     return response.json({'values': values, 'next': values[-1]}, status=200)

    async def get_latest_block(self, request):
        self.driver.clear_pending_state()

        num = storage.get_latest_block_height(self.driver)
        block = self.blocks.get_block(int(num))
        return response.json(block, dumps=encode, headers={'Access-Control-Allow-Origin': '*'})

    async def get_latest_block_number(self, request):
        self.driver.clear_pending_state()

        num = storage.get_latest_block_height(self.driver)

        return response.json({'latest_block_number': num}, headers={'Access-Control-Allow-Origin': '*'})

    async def get_latest_block_hash(self, request):
        self.driver.clear_pending_state()

        return response.json({'latest_block_hash': storage.get_latest_block_hash(self.driver)},
                             headers={'Access-Control-Allow-Origin': '*'})

    async def get_block(self, request):
        num = request.args.get('num')
        _hash = request.args.get('hash')

        if num is not None:
            block = self.blocks.get_block(int(num))
        elif _hash is not None:
            block = self.blocks.get_block(_hash)
        else:
            return response.json({'error': 'No number or hash provided.'}, status=400,
                                 headers={'Access-Control-Allow-Origin': '*'})

        if block is None:
            return response.json({'error': 'Block not found.'}, status=400,
                                 headers={'Access-Control-Allow-Origin': '*'})

        return response.json(block, dumps=encode, headers={'Access-Control-Allow-Origin': '*'})

    async def get_tx(self, request):
        _hash = request.args.get('hash')

        if _hash is not None:
            try:
                int(_hash, 16)
                tx = self.blocks.get_tx(_hash)
            except ValueError:
                return response.json({'error': 'Malformed hash.'}, status=400,
                                     headers={'Access-Control-Allow-Origin': '*'})
        else:
            return response.json({'error': 'No tx hash provided.'}, status=400,
                                 headers={'Access-Control-Allow-Origin': '*'})

        if tx is None:
            return response.json({'error': 'Transaction not found.'}, status=400,
                                 headers={'Access-Control-Allow-Origin': '*'})

        return response.json(tx, dumps=encode, headers={'Access-Control-Allow-Origin': '*'})

    async def get_constitution(self, request):
        self.client.raw_driver.clear_pending_state()

        masternodes = self.client.get_var(
            contract='masternodes',
            variable='S',
            arguments=['members']
        )

        delegates = self.client.get_var(
            contract='delegates',
            variable='S',
            arguments=['members']
        )

        return response.json({
            'masternodes': masternodes,
            'delegates': delegates
        }, headers={'Access-Control-Allow-Origin': '*'})


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description='Standard Lamden HTTP Webserver')

    arg_parser.add_argument('-k', '--key', type=str, required=True)
    arg_parser.add_argument('-p', '--port', type=int, required=False)
    arg_parser.add_argument('-ep', '--event_port', type=int, required=False)

    args = arg_parser.parse_args()

    sk = bytes.fromhex(args.key)
    port = args.port
    event_port = args.event_port

    if port is None:
        port = 18080

    if event_port is None:
        event_port = 8000

    wallet = Wallet(seed=sk)

    # These will be the topics that are sent from the event server
    topics = ["new_block", "block_reorg"]

    webserver = WebServer(
        contracting_client=ContractingClient(),
        driver=storage.ContractDriver(),
        blocks=storage.BlockStorage(),
        wallet=wallet,
        port=port,
        event_service_port=event_port,
        topics=topics
    )

    webserver.app.run(host='0.0.0.0', port=webserver.port, debug=webserver.debug, access_log=webserver.access_log)
