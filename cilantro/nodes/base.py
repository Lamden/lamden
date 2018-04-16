from cilantro import Constants
from cilantro.logger import get_logger
from cilantro.protocol.reactor import NetworkReactor
from cilantro.messages import Envelope, MessageBase
from cilantro.protocol.statemachine import StateMachine


class NodeBase(StateMachine):

    def __init__(self, url=None, signing_key=None):
        self.url = url
        self.signing_key = signing_key
        self.nodes_registry = Constants.Testnet.AllNodes
        self.log = get_logger(type(self).__name__)
        self.reactor = NetworkReactor(self)
        super().__init__()

    def route(self, msg: MessageBase):
        if type(msg) in self.state._receivers:
            self.log.debug("Routing msg: {}".format(msg))
            try:
                self.state._receivers[type(msg)](self.state, msg)
            except Exception as e:
                self.log.error("ERROR ROUTING MSG ... {}".format(e))
        else:
            self.log.error("Message {} has no implemented receiver for state {} in receivers {}"
                           .format(msg, self.state, self.state._receivers))

    def route_req(self, msg: MessageBase, url: str, id: bytes, uuid):
        self.log.debug("Routing request binary: {} with id={} and url={} and uuid={}".format(msg, id, url, uuid))
        if type(msg) not in self.state._repliers:
            self.log.error("Message {} has no implemented replier for state {} in replier {}"
                           .format(msg, self.state, self.state._repliers))
            return

        try:
            reply = self.state._repliers[type(msg)](self.state, msg, id)
            self.log.debug("Replying to id {} with data {}".format(id, reply))
            if reply is None:
                self.log.debug("No reply returned for msg {}".format(msg))
            else:
                assert issubclass(type(reply), MessageBase), "Reply must be a subclass of messagebase"
                assert type(reply) is not Envelope, "Must reply with a message base instance but not an envelope"
                env = Envelope.create(reply, uuid=uuid)
                self.reactor.reply(url=url, id=id, data=env)
        except Exception as e:
            self.log.error("ERROR REPLYING TO MSG ... {}".format(e))

    def route_timeout(self, msg: MessageBase, url):
        self.log.critical("Msg timed out on url {} ...routing msg to timeout handler, {}".format(url, msg))
        if type(msg) not in self.state._timeouts:
            self.log.error("No timeout handler found for msg type {} in handlers {}"
                           .format(type(msg), self.state._timeouts))
            return

        self.state._timeouts[type(msg)](self.state, msg)

    async def route_http(self, request):
        content = await request.content.read()

        try:
            env = Envelope.from_bytes(content)
            msg = env.open()
        except Exception as e:
            self.log.error("Error opening envelope from HTTP POST request...error: {}".format(e))
            return

        self.route(msg)