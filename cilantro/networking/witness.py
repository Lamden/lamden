import zmq
from cilantro.proofs.pow import fishfish
from cilantro.serialization import JSONSerializer


'''
    Witness
    
    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes. 
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate transactions
    that include stake reserves being spent by users staking on the network.  
'''

class Witness(object):
    def __init__(self, host='127.0.0.1', sub_port='4444', serializer=JSONSerializer):
        self.host = host
        self.sub_port = sub_port
        self.pub_port = '4488'
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)
        self.pub_url = 'tcp://{}:{}'.format(self.host, self.pub_port)

        self.serializer = serializer

        self.context = zmq.Context()
        self.witness_sub = self.context.socket(zmq.SUB)

        self.transaction_filter = '0x' # a filter will ensure that only transaction data will be accepted by witnesses for safety
        self.transaction_length = 32 # standard length for transaction data that can be used as an additional filter (safeguard)
        self.witness_sub.setsockopt_string(zmq.SUBSCRIBE, self.transaction_filter, self.transaction_length) # generate witness setting with filters to receive tx data only, of the right size, to avoid spam

    def accept_incoming_transactions(self):
        try:
            self.witness_sub.connect(self.sub_url)
            tx = self.witness_sub.recv_string(flags=zmq.ZMQ_DONTWAIT, encoding='utf-8')

        except Exception as e:
            return {'status': 'Could not receive transaction'}

        raw_tx = None
        try:
            raw_tx = JSONSerializer.deserialize(tx)
        except:
            return {'status': 'Could not deserialize transaction'}

        while True:
            if tx != -1:
                if self.check_user_stake(raw_tx.payload['payload']['from']):
                    if raw_tx.payload['payload']['amount'] < self.check_user_stake(raw_tx.payload['payload']['from']):
                        """if sender has stake and is trying to spend a portion of it they can skip the hashcash check"""
                        self.confirmed_transaction_routine()
                    else:
                        """if sender has a stake but spends more than the entire stake then they go through the proof concept and get their balance check like regular users. needs to be secure."""
                        pass
                if fishfish.TwofishPOW.check(raw_tx, raw_tx.payload['metadata']['proof']):
                    self.confirmed_transaction_routine()

    def activate_witness_publisher(self):
        """Routine to turn witness behavior from masternode subscriber to publisher for delegates by changing port"""
        self.witness_pub = self.context.socket(zmq.PUB)
        self.witness_pub.bind(self.pub_url)

    def confirmed_transaction_routine(self, raw_tx):
        """take approvated transaction data, serialize it, and open publisher socket. publish along tx info to delegate sub and then unbind socket"""
        tx_to_delegate = JSONSerializer.serialize(raw_tx)
        self.activate_witness_publisher()
        self.witness_pub.send_string(tx_to_delegate, encoding='utf-8')
        self.witness_pub.unbind(self.pub_url) #unbind socket

    def check_user_stake(self, tx_sender_address):
        """Check if tx sender has a stake and if sender does, and amount spent is less than stake, bypass hashcash check and allow tx to go directly to witnesses"""
        if tx_sender_address.staking:
            return tx_sender_address.stake
        else:
            return False

# include safeguard to make sure witness and masternode start at the same time and no packets are lost
# add proxy/broker based solution to ensure dynamic discovery between masternodes and witnesses - solved via masternode acting as bootnode

















