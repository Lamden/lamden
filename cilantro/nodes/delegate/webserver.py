from sanic import Sanic
from sanic.response import json, text

app = Sanic(__name__)


@app.route("/", methods=["GET"])
async def ping():
    return text('pong')


@app.route('/balance', methods=['GET'])
async def balance(request):
    return text('pong')


@app.route('/contract', methods=['GET'])
async def contract(request):
    return text('pong')


@app.route('/state', methods=['GET'])
async def state(request):
    return text(request)