from cilantro.nodes.base import BaseNode
from cilantro import Constants

Serializer = Constants.Protocol.Serialization
Proof = Constants.Protocol.Proofs

'''
    Witness
    
    Witnesses exist primarily to check the validity of proofs of transaction sent out by masternodes. 
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate 
    transaction that include stake reserves being spent by users staking on the network.  
'''

class Witness(BaseNode):
    def __init__(self):
        BaseNode.__init__(self,
                          host=Constants.Witness.Host,
                          sub_port=Constants.Witness.SubPort,
                          pub_port=Constants.Witness.PubPort,
                          serializer=Serializer)
        self.hasher = Proof

    async def handle_req(self, data: bytes):
        try:
            unpacked_data = self.serializer.deserialize(data)
        except Exception as e:
            return {'status': 'Could not deserialize transaction'}
        payload_bytes = self.serializer.serialize(unpacked_data["payload"])

        if self.hasher.check(payload_bytes, unpacked_data['metadata']['proof']):
            return self.publish_req(unpacked_data)
        else:
            print('Error: Witness could not confirm transaction POW')
            return {'status': 'invalid proof'}

# include safeguard to make sure witness and db start at the same time and no packets are lost
# add broker based solution to ensure dynamic discovery  - solved via db acting as bootnode
# add proxy/broker based solution to ensure dynamic discovery between witness and db










