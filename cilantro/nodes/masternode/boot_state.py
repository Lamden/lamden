from cilantro import Constants
from cilantro.db import *
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import *
from cilantro.utils import Hasher
from cilantro.messages import *
from aiohttp import web
import asyncio
from cilantro.protocol.structures import MerkleTree

from cilantro.nodes.masternode.base_state import MNBaseState
from cilantro.nodes.masternode.run_state import MNRunState
from cilantro.nodes.masternode.new_block_state import MNNewBlockState


class MNBootState(MNBaseState):
    def reset_attrs(self):
        pass

    @enter_from_any
    def enter_any(self, prev_state):
        self.log.critical("MN IP: {}".format(self.parent.ip))

        # Add publisher socket
        self.parent.composer.add_pub(ip=self.parent.ip)

        # Add router socket
        self.parent.composer.add_router(ip=self.parent.ip)

        # Once done booting, transition to run
        self.parent.transition(MNRunState)

    @exit_from_any
    def exit_any(self, next_state):
        self.log.debug("Bootstate exiting for next state {}".format(next_state))

    @input(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.log.warning("MN BootState not configured to recv transactions")