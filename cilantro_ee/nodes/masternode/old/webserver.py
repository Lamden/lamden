from sanic import Sanic
from sanic import response
#from secure import SecureHeaders
from cilantro_ee.logger.base import get_logger
from sanic_cors import CORS
import json as _json
from contracting.client import ContractingClient

from cilantro_ee.constants import conf
from cilantro_ee.messages.capnp_impl.capnp_impl import pack
from cilantro_ee.storage.master import MasterStorage
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.core.nonces import NonceManager

from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.messages.message import Message

from multiprocessing import Queue
import ast
import ssl

import hashlib

WEB_SERVER_PORT = 8080
SSL_WEB_SERVER_PORT = 443
NUM_WORKERS = 2

app = Sanic(__name__)

ssl_enabled = False
ssl_cert = '~/.ssh/server.csr'
ssl_key = '~/.ssh/server.key'

CORS(app, automatic_options=True)
log = get_logger("MN-WebServer")
client = ContractingClient()
metadata_driver = MetaDataStorage()
nonce_manager = NonceManager()

static_headers = {}


# @app.middleware('response')
# async def set_secure_header(request, response):
#     SecureHeaders.sanic(response)

@app.route("/")
async def hello(request):
    return response.text("hello world")

# ping to check whether server is online or not
@app.route("/ping", methods=["GET","OPTIONS",])
async def ping(request):
    return response.json({'Hello', True})


@app.route('/id', methods=['GET'])
async def get_id(request):
    return response.json({'verifying_key': conf.HOST_VK})


@app.route('/nonce/<vk>', methods=['GET'])
async def get_nonce(request, vk):
    # Might have to change this sucker from hex to bytes.
    pending_nonce = nonce_manager.get_pending_nonce(processor=conf.HOST_VK, sender=bytes.fromhex(vk))

    log.info('Pending nonce: {}'.format(pending_nonce))

    if pending_nonce is None:
        nonce = nonce_manager.get_nonce(processor=conf.HOST_VK, sender=bytes.fromhex(vk))
        log.info('Pending nonce was none so got nonce which is {}'.format(nonce))
        if nonce is None:
            pending_nonce = 0
            log.info('Nonce was now so pending nonce is now zero.')
        else:
            pending_nonce = nonce
            log.info('Nonce was not none so setting pending nonce to it.')

    return response.json({'nonce': pending_nonce, 'processor': conf.HOST_VK.hex(), 'sender': vk})


@app.route('/epoch', methods=['GET'])
async def get_epoch(request):
    epoch_hash = metadata_driver.latest_epoch_hash
    block_num = metadata_driver.latest_block_num

    e = (block_num // conf.EPOCH_INTERVAL) + 1
    blocks_until_next_epoch = (e * conf.EPOCH_INTERVAL) - block_num

    return response.json({'epoch_hash': epoch_hash.hex(),
                 'blocks_until_next_epoch': blocks_until_next_epoch})


@app.route("/", methods=["POST","OPTIONS",])
async def submit_transaction(request):
    if app.queue.full():
        return response.json({'error': "Queue full. Resubmit shortly."}, status=503)

    # Try to deserialize transaction.
    try:
        tx_bytes = request.body
        tx = Message.unpack_message(pack(int(MessageType.TRANSACTION)), tx_bytes)

    except Exception as e:
        return response.json({'error': 'Malformed transaction.'.format(e)}, status=400)

    # Try to put it in the request queue.
    try:
        app.queue.put_nowait(tx)
    except:
        return response.json({'error': "Queue full. Resubmit shortly."}, status=503)

    h = hashlib.sha3_256()
    h.update(tx_bytes)
    tx_hash = h.digest()

    return response.json({'success': 'Transaction successfully submitted to the network.',
                 'hash': tx_hash.hex()})


# Returns {'contracts': JSON List of strings}
@app.route('/contracts', methods=['GET'])
async def get_contracts(request):
    contracts = client.get_contracts()
    return response.json({'contracts': contracts})


@app.route('/contracts/<contract>', methods=['GET'])
async def get_contract(request, contract):
    contract_code = client.raw_driver.get_contract(contract)

    if contract_code is None:
        return response.json({'error': '{} does not exist'.format(contract)}, status=404)
    return response.json({'name': contract, 'code': contract_code}, status=200)


@app.route("/contracts/<contract>/methods", methods=['GET'])
async def get_methods(request, contract):
    contract_code = client.raw_driver.get_contract(contract)

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


@app.route('/contracts/<contract>/<variable>')
async def get_variable(request, contract, variable):
    contract_code = client.raw_driver.get_contract(contract)

    if contract_code is None:
        return response.json({'error': '{} does not exist'.format(contract)}, status=404)

    key = request.args.get('key')

    k = client.raw_driver.make_key(key=contract, field=variable, args=key)
    response = client.raw_driver.get(k)

    if response is None:
        return response.json({'value': None}, status=404)
    else:
        return response.json({'value': response}, status=200)


# Expects json object such that:
'''
{
    'name': 'string',
    'code': 'string'
}
'''

@app.route("/latest_block", methods=["GET","OPTIONS",])
async def get_latest_block(request):
    index = MasterStorage.get_last_n(1)
    latest_block_hash = index.get('blockHash')
    return response.json({ 'hash': '{}'.format(latest_block_hash) })


@app.route('/blocks', methods=["GET","OPTIONS",])
async def get_block(request):
    if 'number' in request.json:
        num = request.json['number']
        block = MasterStorage.get_block(num)
        if block is None:
            return response.json({'error': 'Block at number {} does not exist.'.format(num)}, status=400)
    # TODO check block by hash isn't implemented
    # else:
    #     _hash = request.json['hash']
    #     block = MasterStorage.get_block(hash)
    #     if block is None:
    #         return _respond_to_request({'error': 'Block with hash {} does not exist.'.format(_hash)}, 400)

    return response.json(_json.dumps(block))


def start_webserver(q):
    app.queue = q
    if ssl_enabled:
        context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(ssl_cert, keyfile=ssl_key)
        app.run(host='0.0.0.0', port=SSL_WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False, ssl=context)
    else:
        app.run(host='0.0.0.0', port=WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False)


if __name__ == '__main__':
    import pyximport; pyximport.install()
    if not app.config.REQUEST_MAX_SIZE:
        app.config.update({
            'REQUEST_MAX_SIZE': 10000,
            'REQUEST_TIMEOUT': 20
        })
    start_webserver(Queue())
