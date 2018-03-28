'''
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.

    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving.
'''
from cilantro import Constants
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import State, recv, recv_req, timeout
from cilantro.messages import BlockContender, Envelope, TransactionBase, BlockDataRequest, BlockDataReply
from cilantro.utils import TestNetURLHelper
from aiohttp import web
import asyncio

class MNBaseState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass
    def run(self): pass

    @recv(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.log.critical("mn about to pub")
        self.parent.reactor.pub(url=TestNetURLHelper.pubsub_url(self.parent.url), data=Envelope.create(tx))
        self.log.critical("published on our url: {}".format(TestNetURLHelper.pubsub_url(self.parent.url)))
        return web.Response(text="Successfully published transaction: {}".format(tx))

    @recv(BlockContender)
    def recv_block(self, block: BlockContender):
        self.log.warning("Current state not configured to handle block contender: {}".format(block))

    async def process_request(self, request):
        self.log.warning("Current state not configured to process POST request {}".format(request))


class MNBootState(MNBaseState):
    def enter(self, prev_state):
        self.log.critical("MN URL: {}".format(self.parent.url))
        self.parent.reactor.add_pub(url=TestNetURLHelper.pubsub_url(self.parent.url))
        self.parent.reactor.add_router(url=TestNetURLHelper.dealroute_url(self.parent.url))

    def run(self):
        self.parent.transition(MNRunState)

    def exit(self, next_state):
        self.parent.reactor.notify_ready()

    @recv(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.log.warning("MN BootState not configured to recv transactions")


class MNRunState(MNBaseState):
    def enter(self, prev_state):
        self.app = web.Application()
        self.app.router.add_post('/', self.parent.route_http)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def run(self):
        self.log.info("Starting web server")
        web.run_app(self.app, host=Constants.Testnet.Masternode.Host,
                    port=int(Constants.Testnet.Masternode.ExternalPort))
        # ^ this blocks I think? Or maybe not cause he's on a new event loop..?

    def exit(self, next_state):
        pass
        # TODO -- stop web server, event loop
        # Or is it blocking? ...
        # And if its blocking that means we can't receive on ZMQ sockets right?

    # @recv(TransactionBase)
    # def recv_tx(self, tx: TransactionBase):
    #     self.parent.reactor.pub(url=self.parent.url, data=Envelope.create(tx))
    #     return web.Response(text="Successfully published transaction: {}".format(tx._data))

    @recv(BlockContender)
    def recv_block(self, block: BlockContender):
        self.log.critical("Masternode received block contender: {}".format(block))

        # Loop through signatures in block contender, verify each, and add them to dict of potential nodes to query
        # Start building block by requesting from these nodes
        # Once done, inform nodes of state updates

    @recv(BlockDataReply)
    def recv_blockdata_reply(self, reply: BlockDataReply):
        pass

    @timeout(BlockDataRequest)
    def bc_timeout(self, request: BlockDataRequest):
        pass


class MNNewBlockState(MNBaseState): pass



class Masternode(NodeBase):
    _INIT_STATE = MNBootState
    _STATES = [MNBootState, MNRunState]
    def __init__(self, url=Constants.Testnet.Masternode.InternalUrl, signing_key=Constants.Testnet.Masternode.Sk):
        super().__init__(url=url, signing_key=signing_key)
