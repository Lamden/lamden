"""
    Delegates

    Delegates are the "miners" of the Cilantro blockchain in that they opportunistically bundle up transaction into
    blocks and are rewarded with TAU for their actions. They receive approved transaction from TESTNET_DELEGATES and broadcast
    blocks based on a 1 second or 10,000 transaction limit per block. They should be able to connect/drop from the
    network seamlessly as well as coordinate blocks amongst themselves.

     Delegate logic:
        Step 1) Delegate takes 10k transaction from witness and forms a block
        Step 2) Block propagates across the network to other TESTNET_DELEGATES
        Step 3) Delegates pass around in memory DB hash to confirm they have the same blockchain state
        Step 4) Next block is mined and process repeats

        zmq pattern: subscribers (TESTNET_DELEGATES) need to be able to communicate with one another. this can be achieved via
        a push/pull pattern where all TESTNET_DELEGATES push their state to sink that pulls them in, but this is centralized.
        another option is to use ZMQ stream to have the tcp sockets talk to one another outside zmq
"""

from cilantro.nodes.base import NodeBase, NodeTypes
from cilantro.nodes.delegate.block_manager import BlockManager
from cilantro.storage.vkbook import VKBook


class Delegate(NodeBase):
    def start(self):
        self.bm = BlockManager(ip=self.ip, manager=self.manager)  # This blocks

