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
# from cilantro.nodes.constants import FAUCET_PERCENT
# END DEMO IMPORT
from cilantro.logger.base import get_logger
web.asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from cilantro import Constants
Wallet = Constants.Protocol.Wallets
Proof = Constants.Protocol.Proofs


class Masternode(Node):
    def __init__(self, base_url=Constants.Masternode.Host, internal_port='9999', external_port='8080'):
        Node.__init__(self, base_url=base_url, pub_port=internal_port)
        self.external_port = external_port
        self.logger = get_logger('masternode')

    def zmq_callback(self, msg):
        pass

    def pipe_callback(self, msg):
        print('Publishing message: ', msg)
        self.logger.info('Publishing message: {}'.format(msg))
        self.pub_socket.send(msg)

    async def process_request(self, request):
        print('Got request: ', request)
        self.logger.info('Got request: {}'.format(request))
        self.parent_pipe.send(await request.content.read())
        return web.Response(text=str(request))

    def setup_web_server(self):
        self.start()
        app = web.Application()
        app.router.add_post('/', self.process_request)
        web.run_app(app, host=self.base_url, port=int(self.external_port))
