from sanic import Sanic
from sanic.response import json, text
from cilantro.logger.base import get_logger
from cilantro.messages.transaction.container import TransactionContainer
from cilantro.constants.masternode import WEB_SERVER_PORT
from cilantro.protocol.states.statemachine import StateMachine
from cilantro.protocol.states.state import StateInput
from cilantro.messages.signals.kill_signal import KillSignal
import traceback, multiprocessing, os, asyncio
from collections import deque

app = Sanic(__name__)
app.queue = deque()
log = get_logger(__name__)

@app.route("/", methods=["POST",])
async def transaction(request):
    async def _transaction(req):
        tx_bytes = req.body
        container = TransactionContainer.from_bytes(tx_bytes)
        tx = container.open()
        app.queue.append(tx)
    await _transaction(request)
    return text('received tx')

@app.route("/queue", methods=["GET",])
async def get_queue(request):
    return json({'queue': len(app.queue)})

@app.route("/teardown-network", methods=["POST",])
async def teardown_network(request):
    tx = KillSignal.create()
    return text('tearing down network')

def start_webserver():
    log.debug("Creating REST server on port {}".format(WEB_SERVER_PORT))
    app.run(host='0.0.0.0', port=WEB_SERVER_PORT, workers=2)

if __name__ == '__main__':
    start_webserver()
