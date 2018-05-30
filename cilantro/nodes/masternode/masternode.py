"""
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.

    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving.
"""
from cilantro import Constants
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import *
from cilantro.messages import *
from aiohttp import web


MNNewBlockState = 'MNNewBlockState'


class Masternode(NodeBase):

    async def route_http(self, request):
        # self.log.debug("Got request {}".format(request))
        raw_data = await request.content.read()

        # self.log.debug("Got raw_data: {}".format(raw_data))
        container = TransactionContainer.from_bytes(raw_data)

        # self.log.debug("Got container: {}".format(container))
        tx = container.open()
        self.log.debug("Masternode got tx: {}".format(tx))

        import traceback
        try:
            self.state.call_input_handler(message=tx, input_type=StateInput.INPUT)
            return web.Response(text="Successfully published transaction: {}".format(tx))
        except Exception as e:
            self.log.error("\n Error publishing HTTP request...err = {}".format(traceback.format_exc()))
            return web.Response(text="fukt up processing request with err: {}".format(e))


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

    @input(BlockDataReply)
    def recv_blockdata_reply(self, reply: BlockDataReply):
        self.log.warning("Current state not configured to handle block data reply {}".format(reply))


@Masternode.register_init_state
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

    @exit_to_any
    def exit_any(self, next_state):
        self.log.debug("Bootstate exiting for next state {}".format(next_state))

    @input(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.log.warning("MN BootState not configured to recv transactions")


@Masternode.register_state
class MNRunState(MNBaseState):
    def reset_attrs(self):
        pass

    @enter_from(MNBootState)
    def enter_from_boot(self, prev_state):
        # Create web server
        self.log.debug("Creating web server")
        server = web.Server(self.parent.route_http)
        server_future = self.parent.loop.create_server(server, "0.0.0.0", 8080)
        self.parent.tasks.append(server_future)

    @enter_from(MNNewBlockState)
    def enter_from_newblock(self, success=False):
        if not success:
            self.log.error("\n\nNewBlockState transitioned back with failure!!!\n\n")

    @input_request(BlockContender)
    def recv_block(self, block: BlockContender):
        self.log.info("Masternode received block contender. Transitioning to NewBlockState".format(block))
        self.parent.transition(MNNewBlockState, block=block)

