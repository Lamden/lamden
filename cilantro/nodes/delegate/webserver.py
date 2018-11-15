from sanic import Sanic
from sanic.response import json, text
from seneca.engine.interpreter import SenecaInterpreter
from multiprocessing import Queue

app = Sanic(__name__)


@app.route("/", methods=["GET"])
async def ping(request):
    return text('pong')


@app.route('/balance', methods=['GET'])
async def balance(request):
    return text('pong')


'''
request = {
    "contract" : "hash goes here"
}

response = raw data of the python code
'''
@app.route('/contract', methods=['GET'])
async def contract(request):
    SenecaInterpreter.setup()
    c = SenecaInterpreter.get_contract_meta(request.json['contract'])
    return text('{}'.format(c))


@app.route('/state', methods=['GET'])
async def state(request):
    # get the smart contract at the given location
    return text(request)

def start_webserver(q):
    app.queue = q
    app.run(host='0.0.0.0', port=8080, workers=2, debug=False, access_log=False)

if __name__ == '__main__':
    start_webserver(Queue())