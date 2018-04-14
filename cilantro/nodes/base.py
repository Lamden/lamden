import asyncio
from cilantro import Constants
from cilantro.logger import get_logger
from cilantro.messages import Envelope, MessageBase, MessageMeta, ReactorCommand, TransactionContainer
from cilantro.protocol.reactor import NetworkReactor
from cilantro.protocol.reactor.executor import *
from cilantro.protocol.statemachine import StateMachine


class NodeBase(StateMachine):

    def __init__(self, url=None, signing_key=None):
        self.url = url
        self.signing_key = signing_key
        self.loop = asyncio.new_event_loop()
        self.nodes_registry = Constants.Testnet.AllNodes
        self.log = get_logger(type(self).__name__)
        self.reactor = NetworkReactor(self, self.loop)
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

    def route(self, metadata: bytes, data: bytes):
        try:
            md = MessageMeta.from_bytes(metadata)
            d = MessageBase.registry[md.type].from_bytes(data)

            # TODO -- check metadata signatures

            assert type(d) in self.state._receivers, "State {} has no implemented receiver for {} in _receivers {}"\
                .format(self.state, type(d), self.state._receivers)
            self.state._receivers[type(d)](self.state, d)

        except Exception as e:
            self.log.error("Error deserializing message with\nerror: {}\nmetadata: {}\ndata: {}\n"
                           .format(e, metadata, data))

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


class Router:
    def __init__(self, parent: StateMachine, reactor: NetworkReactor):
        self.parent = parent
        self.reactor = reactor

    def route(self, *args, **kwargs):
        # forward msg to appropriate decorator on state machine
        pass


class Composer:
    def __init__(self, parent: StateMachine, reactor: NetworkReactor):
        self.parent = parent
        self.reactor = reactor

    def notify_ready(self):
        self.log.critical("NOTIFIY READY")
        # TODO -- implement (add queue of tx, flush on notify ready, pause on notify_pause

    def notify_pause(self):
        self.log.critical("NOTIFY PAUSE")
        # TODO -- implement

    def add_sub(self, url: str, filter: str):
        """
        Starts subscribing to 'url'.
        Requires kwargs 'url' of subscriber (as a string)...callback is optional, and by default will forward incoming messages to the
        meta router built into base node
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=url, filter=filter)
        self.socket.send(cmd.serialize())

    def remove_sub(self, url: str, filter: str):
        """
        Requires kwargs 'url' of sub
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.remove_sub.__name__, url=url, filter=filter)
        self.socket.send(cmd.serialize())

    def pub(self, url: str, filter: str, metadata: MessageMeta, data: MessageBase):
        """
        Publish data 'data on socket connected to 'url'
        Requires kwargs 'url' to publish on, as well as 'data' which is the binary data (type should be bytes) to publish
        If reactor is not already set up to publish on 'url', this will be setup and the data will be published
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__, url=url, filter=filter,
                                    data=data, metadata=metadata)
        self.socket.send(cmd.serialize())

    def add_pub(self, url: str):
        """
        Configure the reactor to publish on 'url'.
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=url)
        self.socket.send(cmd.serialize())

    def remove_pub(self, url: str):
        """
        Close the publishing socket on 'url'
        """
        cmd = ReactorCommand.create(SubPubExecutor.__name__, SubPubExecutor.remove_pub.__name__, url=url)
        self.socket.send(cmd.serialize())

    def add_dealer(self, url: str, id):
        """
        needs 'url', 'callback', and 'id'
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.add_dealer.__name__, url=url, id=id)
        self.socket.send(cmd.serialize())

    def add_router(self, url: str):
        """
        needs 'url', 'callback'
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.add_router.__name__, url=url)
        self.socket.send(cmd.serialize())

    def request(self, url: str, metadata: MessageMeta, data: MessageBase, timeout=0):
        """
        'url', 'data', 'timeout' ... must add_dealer first with the url
        Timeout is a int in miliseconds
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.request.__name__, url=url,
                                    metadata=metadata, data=data, timeout=timeout)
        self.socket.send(cmd.serialize())

    def reply(self, url: str, id: str, metadata: MessageMeta, data: MessageBase):
        """
        'url', 'data', and 'id' ... must add_router first with url
        """
        cmd = ReactorCommand.create(DealerRouterExecutor.__name__, DealerRouterExecutor.reply.__name__, url=url, id=id,
                                    metadata=metadata, data=data)
        self.socket.send(cmd.serialize())