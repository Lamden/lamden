from cilantro import Constants
from cilantro.logger import get_logger
from cilantro.protocol.reactor import NetworkReactor
from cilantro.messages import Envelope
from cilantro.protocol.statemachine import StateMachine


class NodeBase(StateMachine):

    def __init__(self, url=None, signing_key=None):
        self.url = url
        self.signing_key = signing_key
        self.nodes_registry = Constants.Testnet.AllNodes
        self.log = get_logger(type(self).__name__)
        self.reactor = NetworkReactor(self)
        super().__init__()

    def route(self, msg_binary: bytes):
        msg = None
        try:
            envelope = Envelope.from_bytes(msg_binary)
            msg = envelope.open()
        except Exception as e:
            self.log.error("Error opening envelope: {}".format(e))

        if type(msg) in self.state._receivers:
            self.log.debug("Routing msg: {}".format(msg))
            try:
                self.state._receivers[type(msg)](self.state, msg)
            except Exception as e:
                self.log.error("ERROR ROUTING MSG ... {}".format(e))
        else:
            self.log.error("Message {} has no implemented receiver for state {} in receivers {}"
                           .format(msg, self.state, self.state._receivers))

    async def route_http(self, request):
        content = await request.content.read()
        self.route(content)