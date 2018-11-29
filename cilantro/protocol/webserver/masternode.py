from cilantro.logger.base import get_logger
from cilantro.messages.transaction.container import TransactionContainer
from cilantro.constants.masternode import WEB_SERVER_PORT
from cilantro.messages.signals.kill_signal import KillSignal
import traceback, multiprocessing, os, asyncio
from multiprocessing import Queue
from os import getenv as env

from sanic.response import json, text
from sanic.exceptions import ServerError
from cilantro.protocol.webserver.sanic import SanicSingleton
from cilantro.protocol.webserver.validation import *
from seneca.engine.interpreter import SenecaInterpreter
from seneca.engine.interface import SenecaInterface
from cilantro.nodes.masternode.mn_api import StorageDriver

app = SanicSingleton.app
interface = SanicSingleton.interface
log = get_logger(__name__)

# TODO RENAME TO run-contract
@app.route("/", methods=["POST",])
async def contract_tx(request):
    if app.queue.full():
        return text("Queue full! Cannot process any more requests")
    tx_bytes = request.body
    container = TransactionContainer.from_bytes(tx_bytes)
    tx = container.open()
    try: app.queue.put_nowait(tx)
    except: return text("Queue full! Cannot process any more requests")
    # log.important("proc id {} just put a tx in queue! queue = {}".format(os.getpid(), app.queue))
    return json({'message': 'Transaction successfully submitted to the network.'})

@app.route("/submit-contract", methods=["POST",])
async def submit_contract(request):
    try:
        contract_name = validate_contract_name(request.json['contract_name'])
        author = validate_author(request.json['author'])
        code_str = request.json['code_str']
        interface.publish_code_str(contract_name, author, code_str)
    except Exception as e:
        return json({'status': 'failure', 'msg': e})
    return json({'status': 'success', 'contract_name': contract_name})

@app.route("/run-contract", methods=["POST",])
async def run_contract(request):
    pass

@app.route("/latest_block", methods=["GET",])
async def get_latest_block(request):
    latest_block_hash = StorageDriver.get_latest_block_hash()
    return text('{}'.format(latest_block_hash))

@app.route('/blocks', methods=["GET", ])
async def get_block(request):
    if 'number' in request.json:
        num = request.json['number']
        block = StorageDriver.get_block_by_num(num)
        if block is None:
            return text({'error': 'Block at number {} does not exist.'.format(num)})
    else:
        _hash = request.json['hash']
        block = StorageDriver.get_block_by_hash(_hash)
        if block is None:
            return text({'error': 'Block with hash {} does not exist.'.format(_hash)})

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

# TODO Remove DEBUG only WARNING
@app.route("/teardown-network", methods=["POST",])
async def teardown_network(request):
    tx = KillSignal.create()
    return text('tearing down network')

def start_webserver(q):
    app.queue = q
    log.debug("Creating REST server on port {}".format(WEB_SERVER_PORT))
    app.run(host='0.0.0.0', port=WEB_SERVER_PORT, workers=2, debug=False, access_log=False)


if __name__ == '__main__':
    import pyximport; pyximport.install()
    if not app.config.REQUEST_MAX_SIZE:
        app.config.update({
            'REQUEST_MAX_SIZE': 5,
            'REQUEST_TIMEOUT': 5
        })
    start_webserver(Queue())
