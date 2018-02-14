import asyncio
import uvloop
import zmq
from zmq.asyncio import Context
from aiohttp import web
from cilantro.serialization import JSONSerializer
from cilantro.proofs.pow import SHA3POW # Needed for Witness
from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS
from cilantro.db.transaction_queue_db import TransactionQueueDB
from cilantro.interpreters.basic_interpreter import BasicInterpreter
from cilantro.transactions.testnet import TestNetTransaction
from cilantro.networking.constants import MAX_QUEUE_SIZE

import time
import sys
# Using UV Loop for EventLoop, instead aysncio's event loop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
# aiohttp
web.asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class PubSubBase(object):
    def __init__(self, host=None, sub_port=None, pub_port=None, serializer=None):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = pub_port
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)
        self.serializer = serializer

        self.ctx = Context() # same as context variable
        self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
        self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)

        # self.sub_socket = None
        # self.pub_socket = None
        self.loop = None

    def start_async(self):
        try:
            self.loop = asyncio.get_event_loop()  # add uvloop here
            # self.loop.run_until_complete(self.start_subscribing())
            self.loop.create_task(self.start_subscribing())
            self.loop.run_forever()
        except Exception as e:
            print(e)
        finally:
            print("Loop finished")

    async def start_subscribing(self):
        """
        Listen
        :return:
        """
        try:
            # self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
            self.sub_socket.bind(self.sub_url)
            print('start subscribing to url: ' + self.sub_url)
            self.sub_socket.subscribe(b'') # as of 17.0
            # self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')  # no filters applied
        except Exception as e:
            print(e)
            return {'status': 'Could not send '}
        while True:
            print("in the while loop")
            req = await self.sub_socket.recv()
            print('received', req)
            await self.handle_req(req)

    def handle_req(self, data: bytes):
        """
        override
        :param data:
        :return:
        """
        pass

    def serialize(self, data):
        """
        Since the base class takes in a serializer
        :param data:
        :return:
        """
        try:
            d = self.serializer.serialize(data)
        except:
            return {'status': 'Could not serialize data'}
        return d


    def publish_req(self, data: bytes):
        # SERIALIZE Function
        # When you need to serialize.
        # d = self.serialize(data)
        # print('Where you at? ', data)
        try:
            print("in publish request")
            print(data)
            # self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)
            self.pub_socket.connect(self.pub_url)
            # self.pub_socket.send(data)
            self.serializer.send(self.serializer.serialize(data), self.pub_socket)
        except Exception as e:
            print("in publish_req Exception:")
            print(e)
            return {'status': 'Could not send transaction'}
        # finally:
        #     self.pub_socket.close() # stop listening to sub_url
            # self.ctx.destroy()


class Witness2(PubSubBase):
    def __init__(self, host='127.0.0.1', sub_port='9999', pub_port='8888', serializer=JSONSerializer, hasher=SHA3POW):
        PubSubBase.__init__(self, host=host, sub_port=sub_port,pub_port=pub_port, serializer=serializer)
        self.hasher = hasher
        self.counter = 0
        # self.sub_socket = self.ctx.socket(socket_type=zmq.SUB)
        # self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)

    async def handle_req(self, data: bytes):
        """
        async def accept_incoming_transactions(self): after the while loop
        :param data:
        :return:
        """
        print("BEFORE try: handle_req in Witness2")
        print(data)
        try:
            unpacked_data = self.serializer.serialize(data)
            # if raw_tx:
            #     self.confirmed_transaction_routine(raw_tx=raw_tx)
        except Exception as e:
            print(e)
            return{'status': 'Could not deserialize transaction'}
        print("handle_req in Witness2")
        self.counter += 1
        print(self.counter)
        # self.confirmed_transaction_routine(raw_tx=raw_tx)
        # if a:
        payload_bytes = self.serializer.deserialize(unpacked_data['payload']).encode()
        if self.hasher.check(payload_bytes, unpacked_data['metadata']['proof']):
            output = await self.confirmed_transaction_routine(data)
            # return output
        else:
            # return {'status': 'Could not confirm transaction POW'}
            pass

    def activate_witness_publisher(self):
        # self.pub_socket = self.ctx.socket(socket_type=zmq.PUB)
        self.pub_socket.bind(self.pub_url)

    async def confirmed_transaction_routine(self, data: bytes):
        # tx_to_delegate = self.serializer.serialize(raw_tx)
        # self.activate_witness_publisher()
        # await self.pub_socket.send(tx_to_delegate)
        # self.pub_socket.unbind(self.pub_url)  # unbind socket?
        self.publish_req(data)
        return {'success': 'request published yay'}


class Masternode2(PubSubBase):
    def __init__(self, host='127.0.0.1', internal_port='9999', external_port='8080', serializer=JSONSerializer):
        PubSubBase.__init__(self, host=host, pub_port=internal_port, serializer=serializer)
        self.external_port = external_port  # port to run server

    def process_transaction(self, data=None):
        if not self.__validate_transaction_length(data):
            return TX_STATUS['INVALID_TX_SIZE']
        print("")
        d = None
        print('Masternode2 data = ', data)
        try:
            d = self.serializer.serialize(data)
        except:
            return TX_STATUS['SERIALIZE_FAILED']

        if not self.__validate_transaction_fields(d):
            return TX_STATUS['INVALID_TX_FIELDS']
        self.publish_req(data)

    def __validate_transaction_length(self, data: bytes):
        if not data:
            return False
        elif len(data) >= MAX_REQUEST_LENGTH:
            return False
        else:
            return True

    def __validate_transaction_fields(self, data: dict):
        if not data:
            return False
        elif 'to' not in data['payload']:
            return False
        elif 'amount' not in data['payload']:
            return False
        elif 'from' not in data['payload']:
            return False
        else:
            return True

    async def process_request(self, request):
        print(request.content.read())
        r = self.process_transaction(data=await request.content.read())
        return web.Response(text=str(r))

    def setup_web_server(self):
        app = web.Application()
        app.router.add_post('/', self.process_request)
        web.run_app(app, host=self.host, port=int(self.external_port))


class Delegate2(PubSubBase):
    def __init__(self, host='127.0.0.1', sub_port='7777', serializer=JSONSerializer, hasher=SHA3POW):
        PubSubBase.__init__(self, host=host, sub_port=sub_port, serializer=serializer)
        self.hasher = hasher

        self.queue = TransactionQueueDB()
        self.interpreter = BasicInterpreter()

        self.msg_count = 0

    def process_transaction(self, data: bytes=None):
        """
        Processes a transaction from witness. This first feeds it through the interpreter, and if
        no errors are thrown, then adds the transaction to the queue.
        :param data: The raw transaction data, assumed to be in byte format
        :return:
        """
        d, tx = None, None

        try:
            d = self.serializer.serialize(data)
        except Exception as e:
            print("Error in delegate serializing data -- {}\nRaw data: {}".format(e, data))
            return {'status': 'error in deleate deserializing data: {}\nRaw data: {}'.format(e, data)}

        print("Delegate processing tx: {}".format(d))  # Debug

        try:
            tx = TestNetTransaction.from_dict(d)
        except Exception as e:
            print('Error building transaction from dictionary: {}\nerror = {}'.format(d, e))
            return {'status': 'Error building transaction from dictionary: {}\nerror = {}'.format(d, e)}

        try:
            self.interpreter.interpret_transaction(tx)
        except Exception as e:
            print('Error interpreting transaction: {}\nTransaction dict: {}'.format(e, d))
            return {'status': 'error interpreting transaction: {}'.format(e)}

        self.queue.enqueue_transaction(tx.payload['payload'])

        if self.queue.queue_size() > MAX_QUEUE_SIZE:
            print('queue exceeded max size...delegate performing consensus')
            self.perform_consensus()

    def handle_req(self, data=None):
        self.msg_count +=1
        self.process_transaction(data=data)
        print('msg_count = ', self.msg_count)
        # if self.delegate_time() or self.msg_count == 10000:
        #     self.perform_consensus()
        #     self.msg_count = 0

    def perform_consensus(self):
        print('delegate performing consensus...')
        pass

    async def delegate_time(self):
        """Conditions to check that 1 second has passed"""
        start_time = time.time()
        await time.sleep(1.0 - ((time.time() - start_time) % 1.0))
        return True



if __name__ == '__main__':
    # Subscribe
    print("a")
    sub = PubSubBase(host='127.0.0.1', sub_port='7777', pub_port='8888')
    # witness = Witness2(sub_port='7777')
    print("b")
    sub.start_async()
