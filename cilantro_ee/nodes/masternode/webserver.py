from sanic import Sanic
from sanic import response
from cilantro_ee.logger.base import get_logger
# from sanic_cors import CORS
import json as _json
from contracting.client import ContractingClient
from contracting.db.encoder import encode
from cilantro_ee.storage import MasterStorage, BlockchainDriver
from cilantro_ee.crypto.canonical import tx_hash_from_tx
from cilantro_ee.crypto.transaction import transaction_is_valid, \
    TransactionNonceInvalid, TransactionProcessorInvalid, TransactionTooManyPendingException, \
    TransactionSenderTooFewStamps, TransactionPOWProofInvalid, TransactionSignatureInvalid, TransactionStampsNegative

from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import os
import capnp

import ast
import ssl
import asyncio

log = get_logger("MN-WebServer")
transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


class ByteEncoder(_json.JSONEncoder):
    def default(self, o, *args):
        if isinstance(o, bytes):
            return o.hex()

        return super().default(self, o)


class WebServer:
    def __init__(self, contracting_client, driver, wallet, blocks, queue=[], port=8080, ssl_port=443, ssl_enabled=False,
                 ssl_cert_file='~/.ssh/server.csr',
                 ssl_key_file='~/.ssh/server.key',
                 workers=2, debug=True, access_log=False,
                 max_queue_len=10_000,
                 ):

        # Setup base Sanic class and CORS
        self.app = Sanic(__name__)
        self.app.config.update({
            'REQUEST_MAX_SIZE': 10000,
            'REQUEST_TIMEOUT': 5
        })
        #self.cors = CORS(self.app, automatic_options=True)

        # Initialize the backend data interfaces
        self.client = contracting_client
        self.driver = driver
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

        # Latest Block Routes
        self.app.add_route(self.get_latest_block, '/latest_block', methods=['GET', 'OPTIONS', ])
        self.app.add_route(self.get_latest_block_number, '/latest_block_num', methods=['GET'])
        self.app.add_route(self.get_latest_block_hash, '/latest_block_hash', methods=['GET'])

        # General Block Route
        self.app.add_route(self.get_block, '/blocks', methods=['GET'])

        # TX Route
        self.app.add_route(self.get_tx, '/tx', methods=['GET'])

    async def start(self):
        # Start server with SSL enabled or not
        if self.ssl_enabled:
            asyncio.ensure_future(self.app.create_server(host='0.0.0.0', port=self.ssl_port, debug=self.debug,
                                  access_log=self.access_log, ssl=self.context, return_asyncio_server=True))
        else:
            asyncio.ensure_future(self.app.create_server(host='0.0.0.0', port=self.port, debug=self.debug,
                                  access_log=self.access_log, return_asyncio_server=True))

    # Main Endpoint to Submit TXs
    async def submit_transaction(self, request):
        log.info(f'Got req:{request}')
        if len(self.queue) >= self.max_queue_len:
            return response.json({'error': "Queue full. Resubmit shortly."}, status=503)

        # Try to deserialize transaction.
        try:
            tx = transaction_capnp.NewTransaction.from_bytes_packed(request.body)

        except Exception as e:
            return response.json({'error': 'Malformed transaction.'.format(e)}, status=400)

        error = False
        msg = {'error': 'Unknown Error'}
        try:
            transaction_is_valid(tx=tx,
                                 expected_processor=self.wallet.verifying_key(),
                                 driver=self.driver,
                                 strict=True)

        # These exceptions are tested to work in the transaction_is_valid tests
        except TransactionNonceInvalid:
            msg = {'error': 'Transaction nonce is invalid.'}
            error = True
        except TransactionProcessorInvalid:
            msg = {'error': 'Transaction processor does not match expected processor.'}
            error = True
        except TransactionTooManyPendingException:
            msg = {'error': 'Too many pending transactions currently in the block.'}
            error = True
        except TransactionSenderTooFewStamps:
            msg = {'error': 'Transaction sender has too few stamps for this transaction.'}
            error = True
        except TransactionPOWProofInvalid:
            msg = {'error': 'Transaction proof of work is invalid.'}
            error = True
        except TransactionSignatureInvalid:
            msg = {'error': 'Transaction is not signed by the sender.'}
            error = True
        except TransactionStampsNegative:
            msg = {'error': 'Transaction has negative stamps supplied.'}
            error = True

        if error:
            log.error(msg)
            return response.json(msg)

        # Put it in the rate limiter queue.
        log.info('Q TIME')
        self.queue.append(tx)

        tx_hash = tx_hash_from_tx(tx)

        return response.json({'success': 'Transaction successfully submitted to the network.',
                              'hash': tx_hash.hex()})

    # Network Status
    async def ping(self, request):
        return response.json({'status': 'online'})

    # Get VK of this Masternode for Nonces
    async def get_id(self, request):
        return response.json({'verifying_key': self.wallet.verifying_key().hex()})

    # Get the Nonce of a VK
    async def get_nonce(self, request, vk):
        # Might have to change this sucker from hex to bytes.
        pending_nonce = self.driver.get_pending_nonce(processor=self.wallet.verifying_key(), sender=bytes.fromhex(vk))

        log.info('Pending nonce: {}'.format(pending_nonce))

        if pending_nonce is None:
            nonce = self.driver.get_nonce(processor=self.wallet.verifying_key(), sender=bytes.fromhex(vk))
            log.info('Pending nonce was none so got nonce which is {}'.format(nonce))
            if nonce is None:
                pending_nonce = 0
                log.info('Nonce was now so pending nonce is now zero.')
            else:
                pending_nonce = nonce
                log.info('Nonce was not none so setting pending nonce to it.')

        # nonce = self.driver.get_nonce(self.wallet.verifying_key(), bytes.fromhex(vk)) or 0
        #
        # pending_nonce = self.driver.get_pending_nonce(self.wallet.verifying_key(), bytes.fromhex(vk)) or nonce

        return response.json({'nonce': pending_nonce, 'processor': self.wallet.verifying_key().hex(), 'sender': vk})

    # Get all Contracts in State (list of names)
    async def get_contracts(self, request):
        contracts = self.client.get_contracts()
        return response.json({'contracts': contracts})

    # Get the source code of a specific contract
    async def get_contract(self, request, contract):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)
        return response.json({'name': contract, 'code': contract_code}, status=200)

    async def get_methods(self, request, contract):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)

        tree = ast.parse(contract_code)

        function_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]

        funcs = []
        for definition in function_defs:
            func_name = definition.name
            kwargs = [arg.arg for arg in definition.args.args]

            funcs.append({'name': func_name, 'arguments': kwargs})

        return response.json({'methods': funcs}, status=200)

    async def get_variables(self, request, contract):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)

        tree = ast.parse(contract_code)

        assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)]

        variables = []
        hashes = []

        for assign in assigns:
            if type(assign.value) == ast.Call:
                if assign.value.func.id == 'Variable':
                    variables.append(assign.targets[0].id.lstrip('__'))
                elif assign.value.func.id == 'Hash':
                    hashes.append(assign.targets[0].id.lstrip('__'))

        return response.json({
            'variables': variables,
            'hashes': hashes
        })

    async def get_variable(self, request, contract, variable):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)

        key = request.args.get('key')
        if key is not None:
            key = key.split(',')

        k = self.client.raw_driver.make_key(contract=contract, variable=variable, args=key)
        value = self.client.raw_driver.get(k)

        if value is None:
            return response.json({'value': None}, status=404)
        else:
            return response.json({'value': value}, status=200, dumps=encode)

    async def iterate_variable(self, request, contract, variable):
        contract_code = self.client.raw_driver.get_contract(contract)

        if contract_code is None:
            return response.json({'error': '{} does not exist'.format(contract)}, status=404)

        key = request.args.get('key')
        # if key is not None:
        #     key = key.split(',')

        k = self.client.raw_driver.make_key(key=contract, field=variable, args=key)

        values = self.client.raw_driver.iter(k, length=500)

        if len(values) == 0:
            return response.json({'values': None}, status=404)
        return response.json({'values': values, 'next': values[-1][0]}, status=200)

    async def get_latest_block(self, request):
        index = self.blocks.get_last_n(n=1, collection=MasterStorage.BLOCK)
        return response.json(index[0], dumps=ByteEncoder().encode)

    async def get_latest_block_number(self, request):
        return response.json({'latest_block_number': self.driver.get_latest_block_num()})

    async def get_latest_block_hash(self, request):
        return response.json({'latest_block_hash': self.driver.get_latest_block_hash()})

    async def get_block(self, request):
        num = request.args.get('num')
        _hash = request.args.get('hash')

        if num is not None:
            block = self.blocks.get_block(int(num))
        elif _hash is not None:
            block = self.blocks.get_block(_hash)
        else:
            return response.json({'error': 'No number or hash provided.'}, status=400)

        if block is None:
            return response.json({'error': 'Block not found.'}, status=400)

        return response.json(block, dumps=ByteEncoder().encode)

    async def get_tx(self, request):
        _hash = request.args.get('hash')

        if _hash is not None:
            tx = self.blocks.get_tx(bytes.fromhex(_hash))
        else:
            return response.json({'error': 'No tx hash provided.'}, status=400)

        if tx is None:
            return response.json({'error': 'Transaction not found.'}, status=400)

        return response.json(tx, dumps=ByteEncoder().encode)

