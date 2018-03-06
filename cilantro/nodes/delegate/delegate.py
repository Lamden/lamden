from cilantro.nodes import Node
import sys
from cilantro.logger.base import get_logger
from cilantro.models import StandardTransaction
from cilantro import Constants

if sys.platform != 'win32':
    pass


"""
    Delegates

    Delegates are the "miners" of the Cilantro blockchain in that they opportunistically bundle up transaction into 
    blocks and are rewarded with TAU for their actions. They receive approved transaction from delegates and broadcast
    blocks based on a 1 second or 10,000 transaction limit per block. They should be able to connect/drop from the 
    network seamlessly as well as coordinate blocks amongst themselves.
    
     Delegate logic:   
        Step 1) Delegate takes 10k transaction from witness and forms a block
        Step 2) Block propagates across the network to other delegates
        Step 3) Delegates pass around in memory DB hash to confirm they have the same blockchain state
        Step 4) Next block is mined and process repeats

        zmq pattern: subscribers (delegates) need to be able to communicate with one another. this can be achieved via
        a push/pull pattern where all delegates push their state to sink that pulls them in, but this is centralized.
        another option is to use ZMQ stream to have the tcp sockets talk to one another outside zmq
"""


class Delegate(Node):

    def __init__(self):
        Node.__init__(self,
                      base_url=Constants.Delegate.Host,
                      sub_port=Constants.Delegate.SubPort,
                      pub_port=Constants.Delegate.PubPort)

        self.logger = get_logger('delegate')
        self.logger.info('A Delegate has appeared.')

    def zmq_callback(self, msg):
        self.logger.info('Delegate got a message: {}'.format(msg))
        try:
            tx = StandardTransaction.from_bytes(msg)
            self.logger.info('The delegate says: ', tx._data)
        except:
            self.logger.info('Could not deserialize message: {}'.format(msg))

    def pipe_callback(self, msg):
        pass