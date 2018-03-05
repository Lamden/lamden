from cilantro.nodes.base import Node
'''
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes.
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
'''
from cilantro import Constants

Serializer = Constants.Protocol.Serialization
Proof = Constants.Protocol.Proofs



class Witness(Node):
    def __init__(self):
        Node.__init__(self, sub_port=Constants.Witness.SubPort, pub_port=Constants.Witness.PubPort)

        self.hasher = Proof
        self.serializer = Serializer

    def zmq_callback(self, msg):
        try:
            unpacked_data = self.serializer.deserialize(msg)
        except Exception as e:
            return {'status': 'Could not deserialize transaction'}
        payload_bytes = self.serializer.serialize(unpacked_data["payload"])

        if self.hasher.check(payload_bytes, unpacked_data['metadata']['proof']):
            return self.pub_socket.send(unpacked_data)
        else:
            print('Error: Witness could not confirm transaction POW')
            return {'status': 'invalid proof'}












