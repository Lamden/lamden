from cilantro import Constants
from cilantro.protocol.statemachine import *
from cilantro.utils import Hasher
from cilantro.messages import *

from cilantro.nodes.masternode.run_state import MNRunState
from cilantro.nodes.masternode.new_block_state import MNNewBlockState



class MNBaseState(State):
    @input(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.log.critical("mn about to pub for tx {}".format(tx))  # debug line
        self.parent.composer.send_pub_msg(filter=Constants.ZmqFilters.WitnessMasternode, message=tx)

    @input_request(BlockContender)
    def recv_block(self, block: BlockContender):
        self.log.warning("Current state not configured to handle block contender: {}".format(block))

    @input_request(StateRequest)
    def handle_state_req(self, request: StateRequest):
        self.log.warning("Current state not configured to handle state requests {}".format(request))