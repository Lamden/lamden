import zmq
from zmq.asyncio import Context
import asyncio

import sys
if sys.platform != 'win32':
    import uvloop

from cilantro.serialization import JSONSerializer
from cilantro.proofs.pow import SHA3POW
# from cilantro.networking import PubSubBase


'''
    Witness
    
    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes. 
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate 
    transactions that include stake reserves being spent by users staking on the network.  
'''


class Witness(object):
    def __init__(self, host='127.0.0.1', sub_port='9999', serializer=JSONSerializer, hasher=SHA3POW):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = '7777'
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)
        self.serializer = serializer

        self.hasher = hasher

        self.ctx = Context.instance()
        self.witness_sub = self.ctx.socket(socket_type=zmq.SUB)

        self.witness_pub = None
        self.loop = None

    def start_async(self):
        try:
            self.loop = asyncio.get_event_loop()  # add uvloop here
            self.loop.create_task(self.accept_incoming_transactions())
        except Exception as e:
            print(e)
        finally:
            self.loop.stop()

    async def accept_incoming_transactions(self):
        try:
            self.witness_sub.connect(self.sub_url)
            self.witness_sub.setsockopt(zmq.SUBSCRIBE, '')  # no filters applied
        except Exception as e:
            return {'status': 'Could not connect to witness sub socket'}

        # Main loop entry point for witness sub
        while True:
            tx = await self.witness_sub.recv()
            try:
                raw_tx = self.serializer.deserialize(tx)
            except Exception as e:
                return {'status': 'Could not deserialize transaction'}
            if self.hasher.check(raw_tx, raw_tx.payload['metadata']['proof']):
                self.confirmed_transaction_routine()
            else:
                return {'status': 'Could not confirm transaction POW'}

    def activate_witness_publisher(self):
        """Routine to turn witness behavior from masternode subscriber to pub_socket for delegates by changing port"""
        self.witness_pub = self.ctx.socket(socket_type=zmq.PUB)
        self.witness_pub.bind(self.pub_url)

    async def confirmed_transaction_routine(self, raw_tx):
        """
        Take approved transaction data, serialize it, and open pub_socket socket.
        Then publish along tx info to delegate sub and then unbind socket
        """
        tx_to_delegate = self.serializer.serialize(raw_tx)
        self.activate_witness_publisher()
        await self.witness_pub.send(tx_to_delegate)
        self.witness_pub.unbind(self.pub_url)  # unbind socket?

# include safeguard to make sure witness and masternode start at the same time and no packets are lost
# add broker based solution to e nsure dynamic discovery  - solved via masternode acting as bootnode
# add proxy/broker based solution to ensure dynamic discovery between witness and delegate


if __name__ == '__main__':
    # a = Witness()
    # a.start_async()
    a = zmq.Context()
    b = Context()
    print("a")














