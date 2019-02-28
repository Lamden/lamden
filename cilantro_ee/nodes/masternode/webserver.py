from cilantro_ee.logger.base import get_logger

from sanic import Sanic
from cilantro_ee.protocol.webserver.sanic import SanicSingleton
from sanic.response import json, text
from sanic.exceptions import ServerError
from sanic_limiter import Limiter, get_remote_address
from sanic_cors import CORS, cross_origin

from cilantro_ee.messages.transaction.contract import ContractTransaction
from cilantro_ee.messages.transaction.publish import PublishTransaction
from cilantro_ee.messages.transaction.container import TransactionContainer
from cilantro_ee.messages.transaction.ordering import OrderingContainer
from multiprocessing import Queue

from cilantro_ee.nodes.masternode.nonce import NonceManager
from cilantro_ee.constants.ports import WEB_SERVER_PORT, SSL_WEB_SERVER_PORT
from cilantro_ee.constants.masternode import NUM_WORKERS
from cilantro_ee.utils.hasher import Hasher

from multiprocessing import Queue
import os

from cilantro_ee.nodes.masternode.mn_api import StorageDriver
from cilantro_ee.protocol.webserver.validation import *
from cilantro_ee.tools import parse_code_str

import json as _json

ssl = None
app = SanicSingleton.app
CORS(app, automatic_options=True)
interface = SanicSingleton.interface
log = get_logger("MN-WebServer")

# Define Access-Control header(s) to enable CORS for webserver. This should be included in every response
static_headers = {}

if os.getenv('NONCE_ENABLED', False):
    log.info("Nonces enabled.")
    limiter = Limiter(app, global_limits=['60/minute'], key_func=get_remote_address)
else:
    log.warning("Nonces are disabled! Nonce checking as well as rate limiting will be disabled!")
    limiter = Limiter(app, key_func=get_remote_address)

if os.getenv('SSL_ENABLED') == '1':
    log.info("SSL enabled")
    with open(os.path.expanduser("~/.sslconf"), "r") as df:
        ssl = _json.load(df)
else:
    log.info("SSL NOT enabled")


def _respond_to_request(payload, headers={}, status=200, resptype='json'):
    if resptype == 'json':
        return json(payload, headers=dict(headers, **static_headers), status=status)
    elif resptype == 'text':
        return text(payload, headers=dict(headers, **static_headers), status=status)


@app.route("/", methods=["POST","OPTIONS",])
async def submit_transaction(request):
    if app.queue.full():
        return _respond_to_request({'error': "Queue full! Cannot process any more requests"}, status=503)

    try:
        tx_bytes = request.body
        container = TransactionContainer.from_bytes(tx_bytes)
        tx = container.open()  # Deserializing the tx automatically validates the signature and POW
    except Exception as e:
        return _respond_to_request({'error': 'Error opening transaction: {}'.format(e)}, status=400)

    # TODO do we need to do any other validation? tx size? check sufficient stamps?
    # TODO -- check that timestamp on tx meta is within reasonable bound

    # Check the transaction type and make sure we can handle it
    if type(tx) not in (ContractTransaction, PublishTransaction):
        return _respond_to_request({'error': 'Cannot process transaction of type {}'.format(type(tx))}, status=400)

    if os.getenv('NONCE_ENABLED'):
        # Verify the nonce, and remove it from db if its valid so it cannot be used again
        # TODO do i need to make this 'check and delete' atomic? What if two procs request at the same time?
        if not NonceManager.check_if_exists(tx.nonce):
            return _respond_to_request({'error': 'Nonce {} has expired or was never created'.format(tx.nonce)}, status=400)
        log.spam("Removing nonce {}".format(tx.nonce))
        NonceManager.delete_nonce(tx.nonce)

    # TODO @faclon why do we need this if we check the queue at the start of this func? --davis
    ord_container = OrderingContainer.create(tx)
    try: app.queue.put_nowait(ord_container.serialize())
    except: return _respond_to_request({'error': "Queue full! Cannot process any more requests"}, status=503)

    # Return transaction hash and nonce to users (not sure which they will need) --davis
    return _respond_to_request({'success': 'Transaction successfully submitted to the network.',
                 'nonce': tx.nonce, 'hash': Hasher.hash(tx)})


@app.route("/nonce", methods=['GET',"OPTIONS",])
async def request_nonce(request):
    user_vk = request.json.get('verifyingKey')
    if not user_vk:
        return _respond_to_request({'error': "you must supply the key 'verifyingKey' in the json payload"}, status=400)

    nonce = NonceManager.create_nonce(user_vk)
    log.spam("Creating nonce {}".format(nonce))
    return _respond_to_request({'success': True, 'nonce': nonce})


@app.route("/contracts", methods=["GET","OPTIONS",])
async def get_contracts(request):
    r = interface.r.hkeys('contracts')
    result = {}
    r_str = [_r.decode() for _r in r]
    result['contracts'] = sorted(r_str)
    return _respond_to_request(result)


# This is just a test endpoint we use to detect when a web server has come online
@app.route("/ohai", methods=["GET","OPTIONS",])
async def ohai(request):
    return _respond_to_request({'status':'online'})


@app.route("/contracts/<contract>", methods=["GET","OPTIONS",])
async def get_contract_meta(request, contract):
    contract_name = validate_contract_name(contract)
    return _respond_to_request(interface.get_contract_meta(contract_name))


@app.route("/contracts/<contract>/resources", methods=["GET","OPTIONS",])
async def get_contract_meta(request, contract):
    contract_name = validate_contract_name(contract)
    meta = interface.get_contract_meta(contract_name.encode())
    r = list(meta['resources'].keys())
    return _respond_to_request({'resources': r})


@app.route("/contracts/<contract>/methods", methods=["GET","OPTIONS",])
async def get_contract_meta(request, contract):
    contract_name = validate_contract_name(contract)
    meta = interface.get_contract_meta(contract_name.encode())
    return _respond_to_request({'methods': meta['methods']})


def get_keys(contract, resource, cursor=0):
    pattern = '{}:{}:*'.format(contract, resource)
    keys = interface.r.scan(cursor, pattern, 100)
    _keys = keys[1]

    formatted_keys = [k.decode()[len(pattern) - 1:] for k in _keys]

    return {'cursor': keys[0], 'keys': formatted_keys}


@app.route("/contracts/<contract>/<resource>/", methods=["GET","OPTIONS",])
async def get_contract_resource_keys(request, contract, resource):
    r = get_keys(contract, resource)
    return _respond_to_request(r)


@app.route("/contracts/<contract>/<resource>/cursor/<cursor>", methods=["GET","OPTIONS",])
async def get_contract_resource_keys(request, contract, resource, cursor):
    r = get_keys(contract, resource, cursor)
    return _respond_to_request(r)


@app.route("/contracts/<contract>/<resource>/<key>", methods=["GET","OPTIONS",])
async def get_state(request, contract, resource, key):
    value = interface.r.get('{}:{}:{}'.format(contract, resource, key))
    r = {}
    if value is None:
        r['value'] = 'null'
    else:
        r['value'] = value

    return _respond_to_request(r)


@app.route("/latest_block", methods=["GET","OPTIONS",])
@limiter.limit("10/minute")
async def get_latest_block(request):
    latest_block_hash = StorageDriver.get_latest_block_hash()
    return _respond_to_request({ 'hash': '{}'.format(latest_block_hash) })


@app.route('/blocks', methods=["GET","OPTIONS",])
@limiter.limit("10/minute")
async def get_block(request):
    if 'number' in request.json:
        num = request.json['number']
        block = StorageDriver.get_nth_full_block(given_bnum = num)
        if block is None:
            return _respond_to_request({'error': 'Block at number {} does not exist.'.format(num)}, status=400)
    else:
        _hash = request.json['hash']
        block = StorageDriver.get_nth_full_block(given_hash = _hash)
        if block is None:
            return _respond_to_request({'error': 'Block with hash {} does not exist.'.format(_hash)}, 400)

    return _respond_to_request(block)

def get_tx(_hash):
    if not _hash:
        return None
    return StorageDriver.get_transactions(raw_tx_hash=_hash)

"""
Colin McGrath

Needed to separate out the return of the transaction payload and transaction metadata due to the payload not being
JSON serializable (needs to be returned as bytes)
"""
@app.route('/transaction/payload', methods=['POST',"OPTIONS",])
async def get_transaction_payload(request):
    _hash = request.json.get('hash', None)
    if not _hash:
        return _respond_to_request({'error': 'Required argument "hash" not provided'}, status=400)

    tx = get_tx(_hash)
    if tx is None:
        return _respond_to_request({'error': 'Transaction with hash {} does not exist.'.format(_hash)}, status=400)

    return _respond_to_request(tx['transaction'], resptype='text')

@app.route('/transaction', methods=['POST',"OPTIONS",])
async def get_transaction(request):
    if not request.json:
        log.info("Received body on /transaction {}".format(request.body))
        return _respond_to_request({ 'wtf': 'm8' })
    _hash = request.json.get('hash', None)
    if not _hash:
        return _respond_to_request({'error': 'Required argument "hash" not provided'}, status=400)

    tx = get_tx(_hash)
    if tx is None:
        return _respond_to_request({'error': 'Transaction with hash {} does not exist.'.format(_hash)}, status=400)

    # Remove transaction payload from response to make it json serializable
    tx.pop('transaction', None)
    return _respond_to_request(tx)

@app.route('/transactions', methods=['POST',"OPTIONS",])
async def get_transactions(request):
    _hash = request.json['hash']
    txs = StorageDriver.get_transactions(block_hash=_hash)
    if txs is None:
        return _respond_to_request({'error': 'Block with hash {} does not exist.'.format(_hash)}, status=400)
    return _respond_to_request(txs)

@app.route("/teardown-network", methods=["POST","OPTIONS",])
async def teardown_network(request):
    # raise NotImplementedError()
    # tx = KillSignal.create()
    return _respond_to_request({ 'message': 'tearing down network' })

def start_webserver(q):
    app.queue = q
    log.info("Creating REST server on port {}".format(WEB_SERVER_PORT))
    if ssl:
        log.notice("Starting web server with SSL")
        app.run(host='0.0.0.0', port=SSL_WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False, ssl=ssl)
    else:
        log.notice("Starting web server without SSL")
        app.run(host='0.0.0.0', port=WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False)


if __name__ == '__main__':
    import pyximport; pyximport.install()
    if not app.config.REQUEST_MAX_SIZE:
        app.config.update({
            'REQUEST_MAX_SIZE': 5,
            'REQUEST_TIMEOUT': 5
        })
    start_webserver(Queue())
