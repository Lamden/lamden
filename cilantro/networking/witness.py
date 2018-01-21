import zmq
import asyncio
from cilantro.networking import Node

class Witness(Node):
    def __init__(self, masternode_ip, delegate_ip, test_time=0):
        self.masternodes, self.delegates = Witness.connect(masternode_ip, delegate_ip)

        self.loop = asyncio.get_event_loop()
        asyncio.async(self.zmq_listen())

        if test_time == 0:
            self.loop.run_forever()

        else:
            # run for a set time for testing purposes
            pass

    @classmethod
    def connect(cls, masternode_ip, delegate_ip):
        # listen to masternodes, push to delegates
        context = zmq.Context()

        masternodes = context.socket(zmq.PULL)
        masternodes.bind(masternode_ip)

        delegates = context.socket(zmq.PUSH)
        delegates.connect(delegate_ip)

        return masternodes, delegates

    @asyncio.coroutine
    def zmq_listen(self):
        msg = yield from self.masternodes.recv()
        # process message