from cilantro import Constants
from cilantro.nodes.base import Node
from cilantro.models import StandardTransaction

from cilantro.logger.base import get_logger

'''
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes.
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
'''

Proof = Constants.Protocol.Proofs


class Witness(Node):
    def __init__(self, sub_port=Constants.Witness.SubPort, pub_port=Constants.Witness.PubPort):
        Node.__init__(self,
                      sub_port=sub_port,
                      pub_port=pub_port)

        self.hasher = Proof
        self.logger = get_logger('witness')
        self.logger.info('Witness has appeared.')

    def zmq_callback(self, msg):
        # assume standard tx
        self.logger.info('Got a message: {}'.format(msg))
        try:
            tx = StandardTransaction.from_bytes(msg)
            self.logger.info(tx._data)
            self.pub_socket.send(tx.serialize())
        except:
            self.logger.info('Could not deserialize: {}'.format(msg))

    def pipe_callback(self, msg):
        pass
