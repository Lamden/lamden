from cilantro import Constants
from cilantro.logger import get_logger
from cilantro.protocol.transport import Composer
from cilantro.protocol.statemachine import StateMachine
# from cilantro.protocol.reactor.executor import *


class NodeBase(StateMachine):

    def __init__(self, url, signing_key, loop):
        super().__init__()

        self.log = get_logger(type(self).__name__)

        self.url = url
        self.signing_key = signing_key

        self.loop = loop
        self._composer = None

        self.nodes_registry = Constants.Testnet.AllNodes  # TODO move away from this once we get dat good overlay net

    def start(self):
        """
        Kicks off the main event loop, and properly starts the Node. This call will block whatever thread its run on
        until the end of space and time (or until this Node/process is terminated)
        """
        assert self.composer, "Composer property must be set before start is called"

        # Start the state machine
        self.log.critical("Starting state machine")
        super().start()

        # Start the main event loop
        self.log.critical("Starting main event loop")

        self.loop.run_forever()

    @property
    def composer(self):
        return self._composer

    @composer.setter
    def composer(self, val):
        print("\n\n\n SETTING COMPOSER TO VAL: {}\n\n\n".format(val))
        assert isinstance(val, Composer), ".composer property must be a Composer instance"
        assert self.composer is None, "Composer is already set (composer should only be set once during creation)"
        self._composer = val

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

    # def route(self, envelope: Envelope):
    #     assert type(envelope.data) in self.state._receivers, \
    #         "State {} has no implemented receiver for {} in _receivers {}"\
    #             .format(self.state, type(envelope.data), self.state._receivers)
    #
    #     self.state._receivers[type(envelope.data)](self.state, envelope.data)
    #
    # def route_req(self, msg: MessageBase, url: str, id: bytes, uuid):
    #     self.log.debug("Routing request binary: {} with id={} and url={} and uuid={}".format(msg, id, url, uuid))
    #     if type(msg) not in self.state._repliers:
    #         self.log.error("Message {} has no implemented replier for state {} in replier {}"
    #                        .format(msg, self.state, self.state._repliers))
    #         return
    #
    #     try:
    #         # self.state._repliers[type(msg)](self.state, msg, id)
    #         reply = self.state._repliers[type(msg)](self.state, msg, id)
    #         self.log.debug("Replying to id {} with data {}".format(id, reply))
    #         if reply is None:
    #             self.log.debug("No reply returned for msg {}".format(msg))
    #         else:
    #             assert issubclass(type(reply), MessageBase), "Reply must be a subclass of messagebase"
    #             assert type(reply) is not Envelope, "Must reply with a message base instance but not an envelope"
    #             env = Envelope.create(reply, uuid=uuid)
    #             self.reactor.reply(url=url, id=id, data=env)
    #     except Exception as e:
    #         self.log.error("ERROR REPLYING TO MSG ... {}".format(e))

    # def route_timeout(self, msg: MessageBase, url):
    #     self.log.critical("Msg timed out on url {} ...routing msg to timeout handler, {}".format(url, msg))
    #     if type(msg) not in self.state._timeouts:
    #         self.log.error("No timeout handler found for msg type {} in handlers {}"
    #                        .format(type(msg), self.state._timeouts))
    #         return
    #
    #     self.state._timeouts[type(msg)](self.state, msg)




