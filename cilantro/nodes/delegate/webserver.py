from cilantro.protocol.webserver.sanic import SanicSingleton
from sanic.response import json
from seneca.engine.interpreter import SenecaInterpreter
from multiprocessing import Queue
from cilantro.protocol.webserver.validation import *
from cilantro.constants.ports import WEB_SERVER_PORT, SSL_WEB_SERVER_PORT
from cilantro.constants.delegate import NUM_WORKERS

ssl = None
app = SanicSingleton.app
interface = SanicSingleton.interface
log = get_logger(__name__)

# Define Access-Control header(s) to enable CORS for webserver. This should be included in every response
static_headers = {
    'Access-Control-Allow-Origin': '*'
}

if os.getenv('SSL_ENABLED'):
    log.info("SSL enabled")
    with open(os.path.expanduser("~/.sslconf"), "r") as df:
        ssl = _json.load(df)

def _respond_to_request(payload, headers={}, status=200):
    return json(payload, headers=dict(headers, **static_headers), status=status)

@app.route("/", methods=["GET"])
async def ping(request):
    return _respond_to_request({ 'message': 'pong' })


@app.route('/balance', methods=['GET'])
async def balance(request):
    return _respond_to_request({ 'message': 'pong' })

@app.route("/contract-data", methods=["GET",])
async def get_contract(request):
    contract_name = validate_contract_name(request.json['contract_name'])
    return _respond_to_request(interface.get_contract_meta(contract_name))

@app.route("/contract-meta", methods=["GET",])
async def get_contract_meta(request):
    contract_name = validate_contract_name(request.json['contract_name'])
    return _respond_to_request(interface.get_contract_meta(contract_name))

@app.route("/state", methods=["GET",])
async def get_contract(request):
    contract_name = validate_contract_name(request.json['contract_name'])
    datatype = request.json['datatype']
    key = validate_key_name(request.json['key'])
    meta = interface.get_contract_meta(contract_name)
    if not meta['datatypes'].get(datatype):
        _respond_to_request({ "error": '"{}" is not a valid datatype'.format(datatype), status=400)
    return _respond_to_request({ 'contract': meta['datatypes'][datatype].get(key) })

def start_webserver(q):
    app.queue = q
    if ssl:
        app.run(host='0.0.0.0', port=SSL_WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False, ssl=ssl)
    else:
        app.run(host='0.0.0.0', port=WEB_SERVER_PORT, workers=NUM_WORKERS, debug=False, access_log=False)

if __name__ == '__main__':
    start_webserver(Queue())
