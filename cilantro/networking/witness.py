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


def confirmed_transaction_routine(raw_tx):
    json_serializer.JSONSerializer.serialize(raw_tx)


def check_user_stake(tx_sender_address):
    """Check if tx sender has a stake and if sender does, and amount spent is less than stake, bypass hashcash check and allow tx to go directly to witnesses"""
    if tx_sender_address.staking:
        return tx_sender_address.stake
    else:
        return False

while True:
    tx = witness.recv_string(zmq.ZMQ_DONTWAIT)
    if tx != -1:
        raw_tx = json_serializer.JSONSerializer.deserialize(tx)
        if check_user_stake(raw_tx.payload['payload']['from']):
            if raw_tx.payload['payload']['amount'] < check_user_stake(raw_tx.payload['payload']['from']):
                confirmed_transaction_routine()
            else:
                """if sender has a stake but spends more than the entire stake then they go through the proof concept and get their balance check like regular users. needs to be secure."""
                pass
        if fishfish.TwofishPOW.check(raw_tx, raw_tx.payload['metadata']['proof']):
            confirmed_transaction_routine()








