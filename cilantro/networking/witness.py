import zmq
from cilantro.proofs.pow import fishfish

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


def confirmed_transaction_routine():
    pass


while True:
    tx = witness.recv_string()
    if tx != -1:
        if fishfish.TwofishPOW.check(tx):
            confirmed_transaction_routine()





