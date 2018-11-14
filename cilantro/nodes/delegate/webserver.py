from sanic import Sanic
from sanic.response import json, text

app = Sanic(__name__)


@app.route("/", methods=["GET"])
async def ping():
    return text('pong')
