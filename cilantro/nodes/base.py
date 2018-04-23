from cilantro import Constants
from cilantro.logger import get_logger
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages import MessageBase, MessageMeta, ReactorCommand, TransactionContainer
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.reactor.executor import *
from cilantro.protocol.statemachine import StateMachine


class NodeBase(StateMachine):

    def __init__(self, url=None, signing_key=None):
        self.url = url
        self.signing_key = signing_key
        self.loop = asyncio.new_event_loop()
        self.nodes_registry = Constants.Testnet.AllNodes
        self.log = get_logger(type(self).__name__)
        self.reactor = ReactorInterface(self, self.loop)
        super().__init__()

    # def route(self, msg: MessageBase):
    #     if type(msg) in self.state._receivers:
    #         self.log.debug("Routing msg: {}".format(msg))
    #         try:
    #             self.state._receivers[type(msg)](self.state, msg)
    #         except Exception as e:
    #             self.log.error("ERROR ROUTING MSG ... {}".format(e))
    #     else:
    #         self.log.error("Message {} has no implemented receiver for state {} in receivers {}"
    #                        .format(msg, self.state, self.state._receivers))

    # def route(self, metadata: bytes, data: bytes):
    #     try:
    #         md = MessageMeta.from_bytes(metadata)
    #         d = MessageBase.registry[md.type].from_bytes(data)
    #
    #         # TODO -- check metadata signatures
    #
    #         assert type(d) in self.state._receivers, "State {} has no implemented receiver for {} in _receivers {}"\
    #             .format(self.state, type(d), self.state._receivers)
    #         self.state._receivers[type(d)](self.state, d)
    #
    #     except Exception as e:
    #         self.log.error("Error deserializing message with\nerror: {}\nmetadata: {}\ndata: {}\n"
    #                        .format(e, metadata, data))

    def route(self, envelope: Envelope):
        assert type(envelope.data) in self.state._receivers, \
            "State {} has no implemented receiver for {} in _receivers {}"\
                .format(self.state, type(envelope.data), self.state._receivers)

        self.state._receivers[type(envelope.data)](self.state, envelope.data)

    def route_req(self, msg: MessageBase, url: str, id: bytes, uuid):
        self.log.debug("Routing request binary: {} with id={} and url={} and uuid={}".format(msg, id, url, uuid))
        if type(msg) not in self.state._repliers:
            self.log.error("Message {} has no implemented replier for state {} in replier {}"
                           .format(msg, self.state, self.state._repliers))
            return

        try:
            # self.state._repliers[type(msg)](self.state, msg, id)
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
        self.log.critical("Got request {}".format(request))
        raw_data = await request.content.read()
        self.log.critical("Got raw_data: {}".format(raw_data))
        container = TransactionContainer.from_bytes(raw_data)
        self.log.critical("Got container: {}".format(container))
        tx = container.open()
        self.log.critical("Got tx: {}".format(tx))
        self.state._receivers[type(tx)](self.state, tx)
        # try:
        #     env = Envelope.from_bytes(content)
        #     msg = env.open()
        # except Exception as e:
        #     self.log.error("Error opening envelope from HTTP POST request...error: {}".format(e))
        #     return
        #
        # self.route(msg)

