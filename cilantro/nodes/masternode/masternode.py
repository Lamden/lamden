'''
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.

    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving.
'''
import uvloop
from cilantro.nodes import Node
from aiohttp import web
from cilantro.logger import get_logger

from cilantro import Constants
Wallet = Constants.Protocol.Wallets
Proof = Constants.Protocol.Proofs

from cilantro.models import Message, StandardTransaction
from cilantro.protocol.statemachine import StateMachine, State


class Masternode(Node, StateMachine):
    def __init__(self, base_url=Constants.Masternode.Host, internal_port='9999', external_port='8080'):
        Node.__init__(self, base_url, pub_port=internal_port, sub_port='5678')
        self.external_port = external_port
        self.log = get_logger('MasterNode')

        STATES = [MNBootState, MNLiveState]
        StateMachine.__init__(self, MNBootState, STATES)

    def zmq_callback(self, msg):
        pass

    def pipe_callback(self, msg):
        print('Publishing message: ', msg)
        self.log.info('Publishing message: {}'.format(msg))
        self.pub_socket.send(msg)

    async def process_request(self, request):
        self.log.info('Got request: {}'.format(request))
        content = await request.content.read()
        print('Got content: ', content)

        # Package transaction in message for delivery
        # We are assume content is the StandardTransaction binary (but irl we should verify this)
        msg = Message.create(StandardTransaction, content)

        self.parent_pipe.send(msg.serialize())
        return web.Response(text=str(request))

    def setup_web_server(self):
        self.log.info("Starting web server...")
        self.start()
        app = web.Application()
        app.router.add_post('/', self.process_request)
        web.run_app(app, host=self.base_url, port=int(self.external_port))


class MNBootState(State):
    name = "MNBootState"

    def __init__(self, state_machine=None):
        super().__init__(state_machine)
        self.log = get_logger("Masternode.BootState")

    def handle_message(self, msg):
        self.log.info("got msg: {}".format(msg))

    def enter(self, prev_state):
        self.log.info("Masternode is booting...")

    def exit(self, next_state):
        self.log.info("Masternode exiting boot procedure...")

    def run(self):
        self.sm.transition(MNLiveState)


class MNLiveState(State):
    name = "MNLiveState"

    def __init__(self, state_machine=None):
        super().__init__(state_machine)
        self.log = get_logger("Masternode.LiveState")

    def handle_message(self, msg):
        self.log.info("got msg: {}".format(msg))

    def enter(self, prev_state):
        self.log.info("Masternode entering live state...")

    def exit(self, next_state):
        self.log.info("Masternode exiting live state...")

    def run(self):
        self.log.info("Masternode live state is running.")