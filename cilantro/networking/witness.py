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


class Witness(BaseNode):
    def __init__(self, host='127.0.0.1', sub_port='9999', pub_port='8888', serializer=JSONSerializer, hasher=SHA3POW):
        BaseNode.__init__(self, host=host, sub_port=sub_port, pub_port=pub_port, serializer=serializer)
        self.hasher = hasher

    async def handle_req(self, data: bytes):
        try:
            unpacked_data = self.serializer.deserialize(data)
        except Exception as e:
            return {'status': 'Could not deserialize transaction'}
        payload_bytes = self.serializer.serialize(unpacked_data["payload"])

        # DEBUG TODO REMOVE
        from cilantro.wallets.ed25519 import ED25519Wallet
        payload_binary = JSONSerializer.serialize(unpacked_data['payload'])
        if not ED25519Wallet.verify(unpacked_data['payload']['from'], payload_binary, unpacked_data['metadata']['signature']):
            print('witness: fail point 1')
        else:
            print("witness works also???")
        # END DEBUG

        if self.hasher.check(payload_bytes, unpacked_data['metadata']['proof']):
            return self.publish_req(unpacked_data)
        else:
            print('Error: Witness could not confirm transaction POW')
            return {'status': 'invalid proof'}

# include safeguard to make sure witness and masternode start at the same time and no packets are lost
# add broker based solution to ensure dynamic discovery  - solved via masternode acting as bootnode
# add proxy/broker based solution to ensure dynamic discovery between witness and delegate










