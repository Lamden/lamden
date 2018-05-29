"""
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.

    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving.
"""
from cilantro import Constants
from cilantro.db import *
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import *
from cilantro.utils import Hasher
from cilantro.messages import *
from aiohttp import web
import asyncio
from cilantro.protocol.structures import MerkleTree

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


class MNNewBlockState(MNBaseState):

    def reset_attrs(self):
        self.pending_blocks = []

    # Development sanity check (remove this in production)
    @enter_from_any
    def enter_any(self, prev_state):
        raise Exception("NewBlockState should only be entered from RunState, but previous state is {}".format(prev_state))

    @enter_from(MNRunState)
    def enter_from_run(self, prev_state, block: BlockContender):
        self.log.debug("Entering NewBlockState with block contender {}".format(block))


    @input(BlockContender)
    def handle_block_contender(self, block: BlockContender):
        if self.validate_block_contender(block):
            self.log.debug("Adding block contender {} ")
            self.pending_blocks.append(block)

    def validate_sigs(self, signatures, msg) -> bool:
        for sig in signatures:
            self.log.info("mn verifying signature: {}".format(sig))
            if not sig.verify(msg, sig.sender):
                self.log.error("!!!! Oh no why couldnt we verify sig {}???".format(sig))
                return False
        return True

    def validate_block_contender(self, block: BlockContender) -> bool:
        """
        Helper method to validate a block contender. For a block contender to be valid it must:
        1) Have a provable merkle tree, ie. all nodes must be hash of (left child + right child)
        2) Be signed by at least 2/3 of the top 32 delegates
        :param block_contender: The BlockContender to validate
        :return: True if the BlockContender is valid, false otherwise
        """
        # Development sanity checks (these should be removed in production)
        assert len(block.nodes) >= 1, "Masternode got block contender with no nodes! {}".format(block)
        assert len(block.signatures) >= Constants.Testnet.Majority, \
            "Received a block contender with only {} signatures (which is less than a majority of {}"\
            .format(len(block.signatures), Constants.Testnet.Majority)

        # Prove Merkle Tree
        hash_of_nodes = Hasher.hash_iterable(block.nodes, algorithm=Hasher.Alg.SHA3_256, return_bytes=True)
        if not MerkleTree.verify_tree(self.tx_hashes, hash_of_nodes):
            self.log.error("\n\n\n\nCOULD NOT VERIFY MERKLE TREE FOR BLOCK CONTENDER {}\n\n\n".format(block))
            return False

        # Validate signatures
        if not self.validate_sigs(block.signatures, hash_of_nodes):
            self.log.error("MN COULD NOT VALIDATE SIGNATURES FOR CONTENDER {}".format(block))
            return False

        return True


class Masternode(NodeBase):
    _INIT_STATE = MNBootState
    _STATES = [MNBootState, MNRunState]

    async def route_http(self, request):
        self.log.debug("Got request {}".format(request))
        raw_data = await request.content.read()

        self.log.debug("Got raw_data: {}".format(raw_data))
        container = TransactionContainer.from_bytes(raw_data)

        self.log.debug("Got container: {}".format(container))
        tx = container.open()

        self.log.debug("Got tx: {}".format(tx))

        import traceback
        try:
            # self.state._receivers[type(tx)](self.state, tx)
            self.state.call_input_handler(message=tx, input_type=StateInput.INPUT)
            return web.Response(text="Successfully published transaction: {}".format(tx))
        except Exception as e:
            self.log.error("\n Error publishing HTTP request...err = {}".format(traceback.format_exc()))
            return web.Response(text="fukt up processing request with err: {}".format(e))
