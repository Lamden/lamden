from sanic import Sanic
from sanic.response import json, text
from secure import SecureHeaders
from cilantro_ee.logger.base import get_logger
from sanic_cors import CORS, cross_origin
import json as _json
from contracting.client import ContractingClient
from cilantro_ee.messages.transaction.contract import ContractTransaction
from cilantro_ee.messages.transaction.container import TransactionContainer
from cilantro_ee.messages.transaction.ordering import OrderingContainer
from cilantro_ee.nodes.masternode.nonce import NonceManager

from cilantro_ee.constants import conf
from cilantro_ee.utils.hasher import Hasher

from cilantro_ee.storage.master import MasterStorage

from multiprocessing import Queue
import ast
import ssl
import time

WEB_SERVER_PORT = 8080
SSL_WEB_SERVER_PORT = 443
NUM_WORKERS = 2

app = Sanic(__name__)

ssl_enabled = False
ssl_cert = '~/.ssh/server.cs,mr'
ssl_key = '~/.ssh/server.key'

CORS(app, automatic_options=True)
log = get_logger("MN-WebServer")
client = ContractingClient()

static_headers = {}


@app.middleware('response')
async def set_secure_headers(request, response):
    SecureHeaders.sanic(response)


def _respond_to_request(payload, headers={}, status=200, resptype='json'):
    if resptype == 'json':
        return json(payload, headers=dict(headers, **static_headers), status=status)
    elif resptype == 'text':
        return text(payload, headers=dict(headers, **static_headers), status=status)


# ping to check whether server is online or not
@app.route("/ping", methods=["GET","OPTIONS",])
async def ping(request):
    return _respond_to_request({'status':'online'})


@app.route("/", methods=["POST","OPTIONS",])
async def submit_transaction(request):
    if app.queue.full():
        return json({'error': "Queue full. Resubmit shortly."}, status=503)

    try:
        tx_bytes = request.body
        tx = ContractTransaction.from_bytes(tx_bytes)
    except Exception as e:
        return json({'error': 'Malformed transaction.'.format(e)}, status=400)

    # TODO @faclon why do we need this if we check the queue at the start of this func? --davis
    ord_container = OrderingContainer.create(tx)
    try:
        app.queue.put_nowait(ord_container.serialize())
    except:
        return json({'error': "Queue full. Resubmit shortly."}, status=503)

    # Return transaction hash and nonce to users (not sure which they will need) --davis
    return json({'success': 'Transaction successfully submitted to the network.',
                 'nonce': tx.nonce, 'hash': Hasher.hash(tx)})


# Returns {'contracts': JSON List of strings}
@app.route('/contracts', methods=['GET'])
async def get_contracts(request):
    contracts = client.get_contracts()
    return json({'contracts': contracts})


@app.route('/contracts/<contract>', methods=['GET'])
async def get_contract(request, contract):
    contract_code = client.raw_driver.get_contract(contract)

    if contract_code is None:
        return json({'error': '{} does not exist'.format(contract)}, status=404)
    return json({'name': contract, 'code': contract_code}, status=200)


@app.route("/contracts/<contract>/methods", methods=['GET'])
async def get_methods(request, contract):
    contract_code = client.raw_driver.get_contract(contract)

    if contract_code is None:
        return json({'error': '{} does not exist'.format(contract)}, status=404)

    tree = ast.parse(contract_code)

    function_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]

    funcs = []
    for definition in function_defs:
        func_name = definition.name
        kwargs = [arg.arg for arg in definition.args.args]

        funcs.append({'name': func_name, 'arguments': kwargs})

    return json({'methods': funcs}, status=200)


@app.route('/contracts/<contract>/<variable>')
async def get_variable(request, contract, variable):
    contract_code = client.raw_driver.get_contract(contract)

    if contract_code is None:
        return json({'error': '{} does not exist'.format(contract)}, status=404)

    key = request.args.get('key')

    if key is None:
        response = client.raw_driver.get('{}.{}'.format(contract, variable))
    else:
        response = client.raw_driver.get('{}.{}:{}'.format(contract, variable, key))

    if response is None:
        return json({'value': None}, status=404)
    else:
        return json({'value': response}, status=200)


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
    return _respond_to_request({ 'hash': '{}'.format(latest_block_hash) })


@app.route('/blocks', methods=["GET","OPTIONS",])
async def get_block(request):
    if 'number' in request.json:
        num = request.json['number']
        block = MasterStorage.get_block(num)
        if block is None:
            return _respond_to_request({'error': 'Block at number {} does not exist.'.format(num)}, status=400)
    else:
        _hash = request.json['hash']
        block = driver().get_block(hash)
        if block is None:
            return _respond_to_request({'error': 'Block with hash {} does not exist.'.format(_hash)}, 400)

    return _respond_to_request(_json.dumps(block))


def start_webserver(q):
    time.sleep(30)
    log.debugv("TESTING Creating REST server on port {}".format(WEB_SERVER_PORT))
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
            'REQUEST_MAX_SIZE': 5,
            'REQUEST_TIMEOUT': 5
        })
    start_webserver(Queue())
