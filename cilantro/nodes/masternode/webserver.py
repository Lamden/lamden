from cilantro.logger.base import get_logger, overwrite_logger_level

from sanic import Sanic
from sanic.response import json, text
from sanic.exceptions import ServerError

from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.publish import PublishTransaction
from cilantro.messages.transaction.container import TransactionContainer
from cilantro.messages.signals.kill_signal import KillSignal

from cilantro.storage.driver import StorageDriver
from cilantro.nodes.masternode.nonce import NonceManager

from cilantro.constants.masternode import WEB_SERVER_PORT, NUM_WORKERS
from cilantro.utils.hasher import Hasher

import traceback, multiprocessing, os, asyncio
from multiprocessing import Queue
import os


app = Sanic(__name__)
log = get_logger(__name__)

if os.getenv('NONCE_DISABLED'):
    log.warning("NONCE_DISABLED env var set! Nonce checking will be disabled!")
else:
    log.info("Nonces enabled.")


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

    # TODO why do we need this if we check the queue at the start of this func? --davis
    try: app.queue.put_nowait(tx)
    except: return json({'error': "Queue full! Cannot process any more requests"})

    # log.important("proc id {} just put a tx in queue! queue = {}".format(os.getpid(), app.queue))
    # TODO return transaction hash or some unique identifier here
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
            return json({'error': 'Block at number {} does not exist.'.format(num)})
    else:
        _hash = request.json['hash']
        block = StorageDriver.get_block_by_hash(_hash)
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
    raise NotImplementedError()
    # tx = KillSignal.create()
    # return text('tearing down network')


def start_webserver(q):
    app.queue = q
    log.info("Creating REST server on port {}".format(WEB_SERVER_PORT))
    app.run(host='0.0.0.0', port=WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False)


if __name__ == '__main__':
    import pyximport; pyximport.install()
    if not app.config.REQUEST_MAX_SIZE:
        app.config.update({
            'REQUEST_MAX_SIZE': 5,
            'REQUEST_TIMEOUT': 5
        })
    start_webserver(Queue())
