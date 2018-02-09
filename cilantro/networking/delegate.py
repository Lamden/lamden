import asyncio
import uvloop
import zmq
from zmq.asyncio import Context

from cilantro.interpreters import TestNetInterpreter

from cilantro.transactions import TestNetTransaction

from cilantro.wallets import ED25519Wallet

from cilantro.serialization import JSONSerializer

from cilantro.networking.constants import MAX_QUEUE_SIZE

from cilantro.proofs.pow import SHA3POW

from cilantro.db.transaction_queue_db import TransactionQueueDB


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())



class Delegate(object):
    def __init__(self, host='127.0.0.1', sub_port='7777', pub_port='5555', serializer=JSONSerializer):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = pub_port

        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)

        self.serializer = serializer

        self.ctx = Context()
        self.delegate_sub = self.ctx.socket(socket_type=zmq.SUB)

        self.queue = TransactionQueueDB()

        self.delegate_pub = None
        self.loop = None

        self.interpreter = TestNetInterpreter()

    def start_async(self):
        try:
            self.loop = asyncio.get_event_loop()  # add uvloop here
            self.loop.create_task(self.accept_incoming_transactions())
        except Exception as e:
            print(e)

    async def accept_incoming_transactions(self):
        try:
            self.delegate_sub.connect(self.sub_url)
            self.delegate_sub.setsockopt(zmq.SUBSCRIBE, '')
        except Exception as e:
            print('Delegate error subscribing to tx: ' + str(e))
            return {'status': 'Could not connect to delegate sub socket'}

        while True:
            tx = await self.delegate_sub.recv()
            raw_tx = None
            try:
                raw_tx = self.serializer.deserialize(tx)
            except Exception as e:
                print('error deserializing tranasction: ' + str(e))
                return {'status': 'Could not deserialize transaction'}

            self.process_transaction(raw_tx)

    def process_transaction(self, data=None):
        """
        :param data: The raw transaction data, assumed to be in byte format
        :return:
        """
        d, tx = None, None

        try:
            d = self.serializer.serialize(data)
        except Exception as e:
            print("Error in delegate serializing data -- {}".format(e))

        print("Delegate processing tx: {}".format(d))

        try:
            tx = TestNetTransaction.from_dict(d)
            interpreter = TestNetInterpreter()
            interpreter.interpret_transaction(tx)
        except Exception as e:
            print('Error interpreting transaction: {}\nTransaction dict: {}'.format(e, d))
            return {'status': 'error interpreting transaction: {}'.format(e)}

        self.queue.enqueue_transaction(tx.payload)

        if self.queue.queue_size() > MAX_QUEUE_SIZE:
            print('queue exceeded max size...delegate performing consensus')
            self.perform_consensus()

    def test_func(self):
        print("hello this is a asdffadsf")


    def perform_consensus(self):
        print('delegate performing consensus...')
        pass



import json

user_post = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto', 'type':'t'}, 'metadata': {'sig':'x287', 'proof': '000'}}
binary_data = json.dumps(user_post).encode()

d = Delegate()
d.process_transaction(data=binary_data)




# async def recv():
#     s = ctx.socket(zmq.SUB)
#     s.connect('tcp://127.0.0.1:9999')
#     s.subscribe(b'w')
#     while True:
#         msg = await s.recv_json()
#         print('received', msg)
#     s.close()

# print('listening for messages...')
# asyncio.get_event_loop().run_until_complete(recv())