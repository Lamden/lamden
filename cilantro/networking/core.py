import zmq
import asyncio
import aiozmq
import uvloop
import time
import multiprocessing

class Node(multiprocessing.Process):
    def __init__(self, *args):
        raise NotImplementedError

    @classmethod
    async def consume(cls):
        raise NotImplementedError