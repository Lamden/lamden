from sanic import Sanic
from sanic.response import json, text
from cilantro.logger.base import get_logger
from cilantro.messages.transaction.container import TransactionContainer
from cilantro.constants.masternode import WEB_SERVER_PORT
from cilantro.protocol.states.statemachine import StateMachine
from cilantro.protocol.states.state import StateInput
import traceback, multiprocessing

app = Sanic(__name__)
q_mode = 0
log = get_logger(__name__)

@app.route("/", methods=["POST",])
async def transaction(request):
    container = TransactionContainer.from_bytes(request.body)
    tx = container.open()
    try:
        sm_handler = StateMachine()
        sm_handler.state.call_input_handler(message=tx, input_type=StateInput.INPUT)
        return text("Successfully published transaction: {}".format(tx))
    except Exception as e:
        log.error("\n Error publishing HTTP request...err = {}".format(traceback.format_exc()))
        return text("problem processing request with err: {}".format(e))

def start_webserver(queue_mode):
    global q_mode
    q_mode = queue_mode
    log.debug("Creating REST server on port {}".format(WEB_SERVER_PORT))
    app.run(host='0.0.0.0', port=WEB_SERVER_PORT, workers=multiprocessing.cpu_count())

if __name__ == '__main__':
    start_webserver(0)
