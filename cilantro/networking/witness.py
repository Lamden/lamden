import zmq
from cilantro.proofs.pow import fishfish
from cilantro.serialization import json_serializer

HOST = '127.0.0.1'
PORT = '4444'
URL = 'tcp://{}:{}'.format(HOST, PORT)

context = zmq.Context()
witness = context.socket(zmq.SUB)
witness.connect(URL)

transaction_filter = '0x' # a filter will ensure that only transaction data will be accepted by witnesses for safety
transaction_length = 32 # standard length for transaction data that can be used as an additional filter (safeguard)

witness.setsockopt_string(zmq.SUBSCRIBE, transaction_filter, transaction_length) # generate witness setting with filters to receive tx data only, of the right size, to avoid spam

# include safeguard to make sure witness and masternode start at the same time and no packets are lost
# add proxy/broker based solution to ensure dynamic discovery between masternodes and witnesses - solved via masternode acting as bootnode


def confirmed_transaction_routine():
    def send_to_delegates():
        pass
    pass


while True:
    tx = witness.recv_string(zmq.ZMQ_DONTWAIT)
    if tx != -1:
        raw_tx = json_serializer.JSONSerializer.deserialize(tx)
        if fishfish.TwofishPOW.check(raw_tx, raw_tx.payload['metadata']['proof']):
            confirmed_transaction_routine()




