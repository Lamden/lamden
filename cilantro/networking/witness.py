from cilantro.serialization import JSONSerializer
from cilantro.proofs.pow import SHA3POW
from cilantro.networking import BaseNode


'''
    Witness
    
    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes. 
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate 
    transactions that include stake reserves being spent by users staking on the network.  
'''

#base_url='127.0.0.1', subscriber_port='9999', publisher_port='9998'

class Witness(BaseNode):
    def __init__(self, base_url='127.0.0.1', subscriber_port='9999', publisher_port='8888', serializer=JSONSerializer, hasher=SHA3POW):
        BaseNode.__init__(self, base_url=base_url, subscriber_port=subscriber_port, publisher_port=publisher_port, serializer=serializer)
        self.hasher = hasher
        self.messages = []

    def process_message_queue(self, msg):
        try:
            unpacked_data = self.serializer.deserialize(msg)
        except Exception as e:
            return {'status': 'Could not deserialize transaction'}
        payload_bytes = self.serializer.serialize(unpacked_data["payload"])

        if self.hasher.check(payload_bytes, unpacked_data['metadata']['proof']):
            return self.handle_request(msg)
        else:
            print('Error: Witness could not confirm transaction POW')
            return {'status': 'invalid proof'}

    def handle_request(self, request):
        # serialize
        # put on queue
        self.messages.append(request)
        self.queue.put(request)

    def process_local_queue(self, msg):
        try:
            self.message_queue.pub_socket.send_json(msg)
        except Exception as e:
            print("error publishing request: {}".format(e))
            return {'status': 'Could not publish request'}

        print("Successfully published request: {}".format(msg))
        return {'status': 'Successfully published request: {}'.format(msg)}

# include safeguard to make sure witness and masternode start at the same time and no packets are lost
# add broker based solution to ensure dynamic discovery  - solved via masternode acting as bootnode
# add proxy/broker based solution to ensure dynamic discovery between witness and delegate










