import asyncio
import uvloop
import zmq
from zmq.asyncio import Context
from cilantro.interpreters import TestNetInterpreter

from cilantro.serialization import JSONSerializer

from cilantro.networking.constants import MAX_QUEUE_SIZE

from cilantro.proofs.pow import SHA3POW

from cilantro.db.balance_db import BalanceDB
from cilantro.db.scratch_db import ScratchDB
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

        self.ctx = Context.instance()
        self.delegate_sub = self.ctx.socket(socket_type=zmq.SUB)

        self.balance = BalanceDB()
        self.scratch = ScratchDB()
        self.queue = TransactionQueueDB()

        self.delegate_pub = None
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

            # do i need to check the hash?
            self.process_transaction(raw_tx)

    async def process_transaction(self, data=None):
        """
        :param data: The raw transaction data, assumed to be in byte format
        :return:
        """
        # TODO -- validate data?

        d = None

        print("Delegate processing tx: {}".format(d))

        try:
            d = self.serializer.serialize(data)
        except Exception as e:
            print("Error in delegate serializing data -- {}".format(e))


        # TODO -- abstract this out into a TransactionParser or TransactionHandler class
        sender = d['payload']['from']
        amount = d['payload']['amount']

        # check if it is in scratch
        if self.scratch.wallet_exists(sender):
            # Is tx valid against scratch?
            scratch_balance = self.scratch.get_balance(sender)
            if scratch_balance - amount >= 0:
                # Update scratch
                self.scratch.set_balance(sender, scratch_balance - amount)
            else:
                return {'status': 'Error: sender does not have enough balance (against scratch)'}
        else:
            # Is tx valid against main db?
            if self.balance.get_balance(sender) >= amount:
                # Update scratch
                balance = self.balance.get_balance(sender)
                self.scratch.set_balance(sender, balance - amount)
            else:
                return {'status': 'Error: sender does not have enough balance (against main balance)'}

        # Add to state change queue
        self.queue.enqueue_transaction(d['payload'])

        if self.queue.queue_size() > MAX_QUEUE_SIZE:
            print('queue exceeded max size...delegate performing consensus')
            self.perform_consensus()

    def perform_consensus(self):
        pass







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