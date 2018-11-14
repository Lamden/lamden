from sanic import Sanic
from sanic.response import json, text
from seneca.engine.interpreter import SenecaInterpreter

app = Sanic(__name__)


@app.route("/", methods=["GET"])
async def ping():
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
    s = SenecaInterpreter()
    c = s.get_code_str(request.json['contract'])
    return text('{}'.format(c))


@app.route('/state', methods=['GET'])
async def state(request):
    # get the smart contract at the given location
    return text(request)