from sanic import Sanic
from sanic.response import json
from cilantro_ee.logger.base import get_logger
from sanic_cors import CORS
from contracting.client import ContractingClient

from cilantro_ee.constants import conf
from cilantro_ee.utils.hasher import Hasher

from multiprocessing import Queue
import ast
import ssl
import time

import hashlib
from cilantro_ee.messages import capnp as schemas
import os
import capnp

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
envelope_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/envelope.capnp')
transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
signal_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/signals.capnp')

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

static_headers = {}


@app.route("/", methods=["POST","OPTIONS",])
async def submit_transaction(request):
    if app.queue.full():
        return json({'error': "Queue full. Resubmit shortly."}, status=503)

    # Try to deserialize transaction.
    try:
        tx_bytes = request.body
        tx = transaction_capnp.ContractTransaction.from_bytes_packed(tx_bytes)

    except Exception as e:
        return json({'error': 'Malformed transaction.'.format(e)}, status=400)

    # Try to put it in the request queue.
    try:
        app.queue.put_nowait(tx)
    except:
        return json({'error': "Queue full. Resubmit shortly."}, status=503)

    h = hashlib.sha3_256()
    h.update(tx_bytes)
    tx_hash = h.digest()

    return json({'success': 'Transaction successfully submitted to the network.',
                 'nonce': tx.payload.nonce.hex(), 'hash': tx_hash.hex()})


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
@app.route('/lint', methods=['POST'])
async def lint_contract(request):
    code = request.json.get('code')

    if code is None:
        return json({'error': 'no code provided'}, status=500)

    violations = client.lint(request.json.get('code'))
    return json({'violations': violations}, status=200)


@app.route('/compile', methods=['POST'])
async def compile_contract(request):
    code = request.json.get('code')

    if code is None:
        return json({'error': 'no code provided'}, status=500)

    violations = client.lint(request.json.get('code'))

    if violations is None:
        compiled_code = client.compiler.parse_to_code(code)
        return json({'code': compiled_code}, status=200)

    return json({'violations': violations}, status=500)


@app.route('/submit', methods=['POST'])
async def submit_contract(request):
    code = request.json.get('code')
    name = request.json.get('name')

    if code is None or name is None:
        return json({'error': 'malformed payload'}, status=500)

    violations = client.lint(code)

    if violations is None:
        client.submit(code, name=name)

    else:
        return json({'violations': violations}, status=500)

    return json({'success': True}, status=200)


@app.route('/exists', methods=['GET'])
async def contract_exists(request):
    contract_code = client.get_contract(request.json.get('name'))

    if contract_code is None:
        return json({'exists': False}, status=404)
    else:
        return json({'exists': True}, status=200)


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
