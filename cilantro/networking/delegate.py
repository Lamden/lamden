import asyncio
import zmq
from zmq.asyncio import Context
from cilantro.serialization import JSONSerializer
from cilantro.proofs.pow import SHA3POW
import time
import sys
if sys.platform != 'win32':
    import uvloop


'''
    Delegates

    Delegates are the "miners" of the Cilantro blockchain in that they opportunistically bundle up transactions into 
    blocks and are rewarded with TAU for their actions. They receive approved transactions from delegates and broadcast
    blocks based on a 1 second or 10,000 transaction limit per block. They should be able to connect/drop from the 
    network seamlessly as well as coordinate blocks amongst themselves. 
'''


class Delegate(object):
    def __init__(self, host='127.0.0.1', sub_port='7777', serializer=JSONSerializer, hasher=SHA3POW):
        self.host = host
        self.sub_port = sub_port
        self.serializer = serializer
        self.hasher = hasher
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)

        self.ctx = Context()
        self.delegate_sub = self.ctx.socket(socket_type=zmq.SUB)

        self.loop = None

    def start_async(self):
        self.loop = asyncio.get_event_loop() # set uvloop here
        self.loop.run_until_complete(self.recv())

    async def recv(self):
        self.delegate_sub.connect(self.sub_url)
        self.delegate_sub.setsockopt(zmq.SUBSCRIBE, b'')

        while True:
            msg_count = 0
            msg = await self.delegate_sub.recv()
            print('received', msg)
            msg_count += 1
            if self.delegate_time() or msg_count == 10000: # conditions for delegate logic go here.
                self.delegate_logic()

    def delegate_logic(self):
            pass

    async def delegate_time(self):
        """Conditions to check that 1 second has passed"""
        starttime = time.time()
        await time.sleep(1.0 - ((time.time() - starttime) % 1.0))
        return True


a = Delegate()
a.start_async()
#a.recv()