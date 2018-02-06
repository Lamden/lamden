import asyncio
import uvloop
import zmq
from zmq.asyncio import Context
from cilantro.interpreters import TestNetInterpreter

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
ctx = Context.instance()

async def recv():
    s = ctx.socket(zmq.SUB)
    s.connect('tcp://127.0.0.1:9999')
    s.subscribe(b'w')
    while True:
        msg = await s.recv_json()
        print('received', msg)
    s.close()

print('listening for messages...')
asyncio.get_event_loop().run_until_complete(recv())
