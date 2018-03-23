'''
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.

    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving.
'''
from cilantro import Constants
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import State, receive
from cilantro.messages import BlockContender, Envelope, TransactionBase
from aiohttp import web
import asyncio

class MNBaseState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass
    def run(self): pass

    @receive(BlockContender)
    def recv_block(self, block: BlockContender):
        self.log.error("Current state not configured to handle block contender: {}".format(block))

    async def process_request(self, request):
        self.log.error("Current state not configured to process POST request {}".format(request))


class MNBootState(MNBaseState):
    def enter(self, prev_state):
        # Publish on our own URL
        self.parent.reactor.add_pub(url=self.parent.url)
        # TODO -- add req/reply endpoints for delegates

    def run(self):
        self.parent.transition(MNRunState)

    def exit(self, next_state):
        self.parent.reactor.notify_ready()


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

    @receive(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.parent.reactor.pub(url=self.parent.url, data=Envelope.create(tx).serialize())
        return web.Response(text="Successfully published transaction: {}".format(tx._data))

    @receive(BlockContender)
    def recv_block(self, block: BlockContender):
        self.log.error("Masternode received block contender: {}".format(block))
        # TODO -- alg to request leaves from delegates and cryptographically verify data


class Masternode(NodeBase):
    _INIT_STATE = MNBootState
    _STATES = [MNBootState, MNRunState]
    def __init__(self, url=Constants.Testnet.Masternode.InternalUrl, signing_key=Constants.Testnet.Masternode.Sk):
        super().__init__(url=url, signing_key=signing_key)
