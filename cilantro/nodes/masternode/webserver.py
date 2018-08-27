from sanic import Sanic
from sanic.response import json, text
from cilantro.logger.base import get_logger
from cilantro.messages.transaction.container import TransactionContainer
from cilantro.constants.masternode import WEB_SERVER_PORT, NUM_WORKERS
from cilantro.messages.signals.kill_signal import KillSignal
import os

# This must be imported for Metaclass registration
from cilantro.messages.transaction.contract import ContractTransaction

app = Sanic(__name__)
log = get_logger(__name__)

@app.route("/", methods=["POST",])
async def contract_tx(request):
    tx_bytes = request.body
    container = TransactionContainer.from_bytes(tx_bytes)
    tx = container.open()
    app.queue.put(tx)
    log.spam("proc id {} just put a tx in queue! queue size = {}".format(os.getpid(), app.queue.qsize()))
    return text('ok put tx in queue...current queue size is {}'.format(app.queue.qsize()))


@app.route("/teardown-network", methods=["POST",])
async def teardown_network(request):
    tx = KillSignal.create()
    return text('tearing down network')


def start_webserver(q):
    app.queue = q
    log.info("Creating Sanic server on port {} with {} workers".format(WEB_SERVER_PORT, NUM_WORKERS))
    app.run(host='0.0.0.0', port=WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False)


if __name__ == '__main__':
    start_webserver()
