import zmq
import asyncio
import aiozmq
import uvloop
import time

class Node(object):
    def __init__(self):
        raise NotImplementedError

    @classmethod
    def connect(cls):
        raise NotImplementedError

    @asyncio.coroutine
    def http_listen(self):
        raise NotImplementedError

    @asyncio.coroutine
    def zmq_listen(self):
        print('test')
        raise NotImplementedError