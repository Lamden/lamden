import zmq
import zmq.asyncio
import asyncio
import uvloop

from cilantro.serialization import JSONSerializer
from cilantro.proofs.pow import SHA3POW


'''
    Witness
    
    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes. 
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate 
    transactions that include stake reserves being spent by users staking on the network.  
'''


class Witness(object):
    def __init__(self, host='127.0.0.1', sub_port='4444', serializer=JSONSerializer, proof=SHA3POW):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = '4488'
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)

        self.serializer = serializer

        self.hasher = proof

        self.context = zmq.asyncio.Context()
        self.witness_sub = self.context.socket(zmq.SUB)

        # a filter will ensure that only transaction data will be accepted by witnesses for safety
        # self.transaction_filter = '0x'
        # standard length for transaction data that can be used as an additional filter (safeguard)
        # self.transaction_length = 32
        # generate witness setting with filters to receive tx data only, of the right size, to avoid spam
        self.witness_sub.setsockopt_string(zmq.SUBSCRIBE, '')

    async def accept_incoming_transactions(self):
        try:
            self.witness_sub.connect(self.sub_url)
        except Exception as e:
            return {'status': 'Could not connect to witness sub socket'}

        # Main loop entry point for witness sub
        while True:
            tx = await self.witness_sub.recv_json(flags=0, encoding='utf-8')
            try:
                raw_tx = self.serializer.deserialize(tx)
            except Exception as e:
                return {'status': 'Could not deserialize transaction'}
            if self.hasher.check(raw_tx, raw_tx.payload['metadata']['proof']):
                self.confirmed_transaction_routine()
            else:
                return {'status': 'Could not confirm transaction POW'}

    def activate_witness_publisher(self):
        """Routine to turn witness behavior from masternode subscriber to publisher for delegates by changing port"""
        self.witness_pub = self.context.socket(zmq.PUB)
        self.witness_pub.bind(self.pub_url)

    async def confirmed_transaction_routine(self, raw_tx):
        """take approvated transaction data, serialize it, and open publisher socket.
         Then publish along tx info to delegate sub and then unbind socket"""
        tx_to_delegate = self.serializer.serialize(raw_tx)
        self.activate_witness_publisher()
        await self.witness_pub.send_json(tx_to_delegate, encoding='utf-8')
        self.witness_pub.unbind(self.pub_url) # unbind socket?


# loop = asyncio.get_event_loop() # add uvloop
# loop.run_forever()


# include safeguard to make sure witness and masternode start at the same time and no packets are lost
# add broker based solution to ensure dynamic discovery  - solved via masternode acting as bootnode
# add proxy/broker based solution to ensure dynamic discovery between witness and delegate



















