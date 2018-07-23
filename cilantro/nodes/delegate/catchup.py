from cilantro import Constants
from cilantro.nodes.delegate.delegate import Delegate, DelegateBaseState
from cilantro.protocol.statemachine import *
from cilantro.protocol.interpreters import VanillaInterpreter
from cilantro.db import *
from cilantro.messages import *


DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"


@Delegate.register_state
class DelegateCatchupState(DelegateBaseState):

    @enter_from_any
    def enter_any(self, prev_state):
        self.log.debug("CatchupState entered from previous state {}".format(prev_state))
        self._request_update()

    def _request_update(self):
        self.parent.current_hash = BlockStorageDriver.get_latest_block_hash()
        self.log.info("Requesting updates from Masternode with current block hash {}".format(self.parent.current_hash))

        request = BlockMetaDataRequest.create(current_block_hash=self.parent.current_hash)
        mn_vk = VKBook.get_masternodes()[0]
        self.parent.composer.send_request_msg(message=request, vk=mn_vk)

    @input(BlockMetaDataReply)
    def handle_blockmeta_reply(self, reply: BlockMetaDataReply):
        self.log.debug("Delegate got BlockMetaDataReply: {}".format(reply))

