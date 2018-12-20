from cilantro.logger.base import get_logger

from sanic import Sanic
from cilantro.protocol.webserver.sanic import SanicSingleton
from sanic.response import json, text
from sanic.exceptions import ServerError
from sanic_limiter import Limiter, get_remote_address

from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.publish import PublishTransaction
from cilantro.messages.transaction.container import TransactionContainer
from cilantro.messages.transaction.ordering import OrderingContainer
from multiprocessing import Queue

from cilantro.nodes.masternode.nonce import NonceManager
from cilantro.constants.ports import WEB_SERVER_PORT, SSL_WEB_SERVER_PORT
from cilantro.constants.masternode import NUM_WORKERS
from cilantro.utils.hasher import Hasher

from multiprocessing import Queue
import os

from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.protocol.webserver.validation import *
from cilantro.tools import parse_code_str

import json as _json

ssl = None
app = SanicSingleton.app
interface = SanicSingleton.interface
log = get_logger("MN-WebServer")

if os.getenv('NONCE_DISABLED'):
    log.warning("NONCE_DISABLED env var set! Nonce checking as well as rate limiting will be disabled!")
    limiter = Limiter(app, key_func=get_remote_address)
else:
    log.info("Nonces enabled.")
    limiter = Limiter(app, global_limits=['60/minute'], key_func=get_remote_address)

if os.getenv('SSL_ENABLED'):
    log.info("SSL enabled")
    with open(os.path.expanduser("~/.sslconf"), "r") as df:
        ssl = _json.load(df)


@app.route("/", methods=["POST",])
async def submit_transaction(request):
    if app.queue.full():
        return json({'error': "Queue full! Cannot process any more requests"})

    try:
        tx_bytes = request.body
        container = TransactionContainer.from_bytes(tx_bytes)
        tx = container.open()  # Deserializing the tx automatically validates the signature and POW
    except Exception as e:
        return json({'error': 'Error opening transaction: {}'.format(e)})

    # TODO do we need to do any other validation? tx size? check sufficient stamps?

    # Check the transaction type and make sure we can handle it
    if type(tx) not in (ContractTransaction, PublishTransaction):
        return json({'error': 'Cannot process transaction of type {}'.format(type(tx))})

    if not os.getenv('NONCE_DISABLED'):
        # Verify the nonce, and remove it from db if its valid so it cannot be used again
        # TODO do i need to make this 'check and delete' atomic? What if two procs request at the same time?
        if not NonceManager.check_if_exists(tx.nonce):
            return json({'error': 'Nonce {} has expired or was never created'.format(tx.nonce)})
        log.spam("Removing nonce {}".format(tx.nonce))
        NonceManager.delete_nonce(tx.nonce)

    # TODO @faclon why do we need this if we check the queue at the start of this func? --davis
    ord_container = OrderingContainer.create(tx)
    try: app.queue.put_nowait(ord_container.serialize())
    except: return json({'error': "Queue full! Cannot process any more requests"})

    # Return transaction hash and nonce to users (not sure which they will need) --davis
    return json({'success': 'Transaction successfully submitted to the network.',
                 'nonce': tx.nonce, 'hash': Hasher.hash(tx)})


@app.route("/nonce", methods=['GET',])
async def request_nonce(request):
    user_vk = request.json.get('verifyingKey')
    if not user_vk:
        return json({'error': "you must supply the key 'verifyingKey' in the json payload"})

    nonce = NonceManager.create_nonce(user_vk)
    log.spam("Creating nonce {}".format(nonce))
    return json({'success': True, 'nonce': nonce})


@app.route("/contracts", methods=["GET", ])
async def get_contracts(request):
    r = interface.r.hkeys('contracts')
    result = {}
    r_str = [_r.decode() for _r in r]
    result['contracts'] = r_str
    return json(result)


@app.route("/contracts/<contract>", methods=["GET", ])
async def get_contract_meta(request, contract):
    contract_name = validate_contract_name(contract)
    return json(interface.get_contract_meta(contract_name))


@app.route("/contracts/<contract>/resources", methods=["GET", ])
async def get_contract_meta(request, contract):
    contract_name = validate_contract_name(contract)
    meta = interface.get_contract_meta(contract_name.encode())
    r = list(meta['resources'].keys())
    return json({'resources': r})


@app.route("/contracts/<contract>/methods", methods=["GET", ])
async def get_contract_meta(request, contract):
    contract_name = validate_contract_name(contract)
    meta = interface.get_contract_meta(contract_name.encode())
    return json({'methods': meta['methods']})


def get_keys(contract, resource, cursor=0):
    pattern = '{}:{}:*'.format(contract, resource)
    keys = interface.r.scan(cursor, pattern, 100)
    _keys = keys[1]

    formatted_keys = [k.decode()[len(pattern) - 1:] for k in _keys]

    return {'cursor': keys[0], 'keys': formatted_keys}


@app.route("/contracts/<contract>/<resource>/", methods=["GET", ])
async def get_contract_resource_keys(request, contract, resource):
    r = get_keys(contract, resource)
    return json(r)


@app.route("/contracts/<contract>/<resource>/cursor/<cursor>", methods=["GET", ])
async def get_contract_resource_keys(request, contract, resource, cursor):
    r = get_keys(contract, resource, cursor)
    return json(r)


@app.route("/contracts/<contract>/<resource>/<key>", methods=["GET",])
async def get_state(request, contract, resource, key):
    value = interface.r.get('{}:{}:{}'.format(contract, resource, key))
    r = {}
    if value is None:
        r['value'] = 'null'
    else:
        r['value'] = value

    return json(r)


@app.route("/latest_block", methods=["GET",])
@limiter.limit("10/minute")
async def get_latest_block(request):
    latest_block_hash = StorageDriver.get_latest_block_hash()
    return text('{}'.format(latest_block_hash))


@app.route('/blocks', methods=["GET", ])
@limiter.limit("10/minute")
async def get_block(request):
    if 'number' in request.json:
        num = request.json['number']
        block = StorageDriver.get_nth_full_block(given_bnum = num)
        if block is None:
            return json({'error': 'Block at number {} does not exist.'.format(num)})
    else:
        _hash = request.json['hash']
        block = StorageDriver.get_nth_full_block(given_hash = hash)
        if block is None:
            return json({'error': 'Block with hash {} does not exist.'.format(_hash)})

    return text('{}'.format(block))


@app.route('/transaction', methods=['GET', ])
async def get_transaction(request):
    _hash = request.json['hash']
    tx = StorageDriver.get_transactions(raw_tx_hash=_hash)
    if tx is None:
        return text({'error': 'Transaction with hash {} does not exist.'.format(_hash)})
    return text('{}'.format(tx))


@app.route('/transactions', methods=['GET', ])
async def get_transactions(request):
    _hash = request.json['hash']
    txs = StorageDriver.get_transactions(block_hash=_hash)
    if txs is None:
        return text({'error': 'Block with hash {} does not exist.'.format(_hash)})
    return text('{}'.format(txs))


@app.route("/teardown-network", methods=["POST",])
async def teardown_network(request):
    # raise NotImplementedError()
    # tx = KillSignal.create()
    return text('tearing down network')


def start_webserver(q):
    app.queue = q
    log.info("Creating REST server on port {}".format(WEB_SERVER_PORT))
    if ssl:
        app.run(host='0.0.0.0', port=SSL_WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False, ssl=ssl)
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
