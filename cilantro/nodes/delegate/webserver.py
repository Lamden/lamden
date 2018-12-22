from cilantro.protocol.webserver.sanic import SanicSingleton
from sanic.response import json, text
from seneca.engine.interpreter import SenecaInterpreter
from multiprocessing import Queue
from cilantro.protocol.webserver.validation import *
from cilantro.constants.ports import WEB_SERVER_PORT, SSL_WEB_SERVER_PORT
from cilantro.constants.delegate import NUM_WORKERS

ssl = None
app = SanicSingleton.app
interface = SanicSingleton.interface
log = get_logger(__name__)

if os.getenv('SSL_ENABLED'):
    log.info("SSL enabled")
    with open(os.path.expanduser("~/.sslconf"), "r") as df:
        ssl = _json.load(df)

@app.route("/", methods=["GET"])
async def ping(request):
    return text('pong')


@app.route('/balance', methods=['GET'])
async def balance(request):
    return text('pong')

@app.route("/contract-data", methods=["GET",])
async def get_contract(request):
    contract_name = validate_contract_name(request.json['contract_name'])
    return json(interface.get_contract_meta(contract_name))

@app.route("/contract-meta", methods=["GET",])
async def get_contract_meta(request):
    contract_name = validate_contract_name(request.json['contract_name'])
    return json(interface.get_contract_meta(contract_name))

@app.route("/state", methods=["GET",])
async def get_contract(request):
    contract_name = validate_contract_name(request.json['contract_name'])
    datatype = request.json['datatype']
    key = validate_key_name(request.json['key'])
    meta = interface.get_contract_meta(contract_name)
    if not meta['datatypes'].get(datatype):
        raise ServerError('"{}" is not a valid datatype'.format(datatype), status_code=500)
    return text(meta['datatypes'][datatype].get(key))

def start_webserver(q):
    app.queue = q
    if ssl:
        app.run(host='0.0.0.0', port=SSL_WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False, ssl=ssl)
    else:
        app.run(host='0.0.0.0', port=WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False)

if __name__ == '__main__':
    start_webserver(Queue())
