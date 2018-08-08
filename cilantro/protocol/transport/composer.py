from cilantro.messages.base.base import MessageBase
from cilantro.protocol.reactor.interface import ReactorInterface
from cilantro.protocol.reactor.executor import ReactorCommand, SubPubExecutor, DealerRouterExecutor
from cilantro.messages.envelope.envelope import Envelope
from cilantro.logger import get_logger
from cilantro.protocol.structures import EnvelopeAuth
from cilantro.protocol import wallet
from cilantro.constants.ports import PUB_SUB_PORT, ROUTER_DEALER_PORT

"""
The Composer class serves as a high level API for a StateMachine (application layer) to execute networking commands on
the ReactorDaemon process. It creates
"""


class Composer:
    def __init__(self, interface: ReactorInterface, signing_key: str, name='Node'):
        super().__init__()
        self.log = get_logger("{}.Composer".format(name))
        self.interface = interface
        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)

    def _package_msg(self, msg: MessageBase) -> Envelope:
        """
        Convenience method to package a message into an envelope
        :param msg: The MessageBase instance to package
        :return: An Envelope instance
        """
        assert type(msg) is not Envelope, "Attempted to package a 'message' that is already an envelope"
        assert issubclass(type(msg), MessageBase), "Attempted to package a message that is not a MessageBase subclass"

        return Envelope.create_from_message(message=msg, signing_key=self.signing_key, verifying_key=self.verifying_key)

    def _package_reply(self, reply: MessageBase, req_env: Envelope) -> Envelope:
        """
        Convenience method to create a reply envelope. The difference between this func and _package_msg, is that
        in the reply envelope the UUID must be the hash of the original request's uuid (not some randomly generated int)
        :param reply: The reply message (an instance of MessageBase)
        :param req_env: The original request envelope (an instance of Envelope)
        :return: An Envelope instance
        """
        self.log.debug("Creating REPLY envelope with msg type {} for request envelope {}".format(type(reply), req_env))
        request_uuid = req_env.meta.uuid
        reply_uuid = EnvelopeAuth.reply_uuid(request_uuid)

        return Envelope.create_from_message(message=reply, signing_key=self.signing_key,
                                            verifying_key=self.verifying_key, uuid=reply_uuid)

    def resume(self):
        self.log.info("Resuming ReactorInterface")
        self.interface.notify_resume()

    def pause(self):
        self.log.info("Pausing ReactorInterface")
        self.interface.notify_pause()

    def add_sub(self, filter: str, ip: str='', vk: str=''):
        """
        Connects the subscriber socket to listen to 'URL' with filter 'filter'.
        :param url: The URL to CONNECT the sub socket to (ex 'tcp://17.1.3.4:4200')
        :param filter: The filter to subscribe to. Only data published with this filter will be received. Currently,
        only one filter per CONNECT is supported.
        """
        # url = "tcp://{}:{}".format(ip or vk, Constants.Ports.PubSub)
        url = "tcp://{}:{}".format(ip or vk, PUB_SUB_PORT)
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, filter=filter, url=url, vk=vk)
        self.interface.send_cmd(cmd)

    def remove_sub(self, ip: str='', vk: str=''):
        """
        Stop subscribing to a URL and filter. Note that all other subscriber connections will drop this filter as well
        (so if there is another URL you are subscribing to with the same filter, that sub will no longer work). The
        pattern at this point is to have a single filter for each 'node type', ie witness/delegate/masternode.

        If you wish to stop subscribing to a URL, but not necessarily a filter, then call this method and pass in an
        empty string to FILTER. For example, a delegate might want to stop subscribing to a particular witness, but not
        all TESTNET_WITNESSES.

        :param filter: The filter to subscribe to. Only multipart messages with this filter as the first frame will be
        received
        :param url: The URL of the router that the created dealer socket should CONNECT to.
        :param vk: The Node's VK to connect to. This will be looked up in the overlay network
        """
        url = "tcp://{}:{}".format(ip or vk, PUB_SUB_PORT)
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.remove_sub.__name__, url=url)
        self.interface.send_cmd(cmd)

    def remove_sub_filter(self, filter: str, ip: str='', vk: str=''):
        """
        Removes a filters from the sub socket. Unlike the remove_sub API, this does not disconnect a URL. It only
        unsubscribes to 'filter
        :param filter: A string to use as the filter frame. This filter will be unsubscribed.
        """
        url = "tcp://{}:{}".format(ip or vk, PUB_SUB_PORT)
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.remove_sub_filter.__name__, url=url, filter=filter)
        self.interface.send_cmd(cmd)

    def send_pub_msg(self, filter: str, message: MessageBase):
        """
        Publish data with filter frame 'filter'. An envelope (including a seal and the metadata) will be created from
        the MessageBase. If you want to send an existing envelope, use send_pub_env
        :param filter: A string to use as the filter frame
        :param message: A MessageBase subclass
        """
        self.send_pub_env(filter=filter, envelope=self._package_msg(message))

    def send_pub_env(self, filter: str, envelope: Envelope):
        """
        Publish envelope with filter frame 'filter'.
        :param filter: A string to use as the filter frame
        :param envelope: An instance of Envelope
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__, filter=filter,
                                        envelope=envelope)
        self.interface.send_cmd(cmd)

    def add_pub(self, ip: str='', vk: str=''):
        """
        Create a publisher socket that BINDS to 'url'
        :param url: The URL to publish under.
        :param vk: The Node's VK to connect to. This will be looked up in the overlay network
        """
        url = "tcp://{}:{}".format(ip or vk, PUB_SUB_PORT)
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=url)
        self.interface.send_cmd(cmd)

    def remove_pub(self, ip: str='', vk: str=''):
        """
        Removes a publisher (duh)
        :param url: The URL of the router that the created dealer socket should CONNECT to.
        :param vk: The Node's VK to connect to. This will be looked up in the overlay network
        """
        url = "tcp://{}:{}".format(ip or vk, PUB_SUB_PORT)
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.remove_pub.__name__, url=url)
        self.interface.send_cmd(cmd)

    def add_dealer(self, ip: str='', vk: str=''):
        """
        Add a dealer socket at url. Dealers are like 'async requesters', and can connect to a single Router socket (1-1)
        (side note: A router socket, however, can connect to N dealers)
        'id' socketopt for the dealer socket will be this node's verifying key
        :param url: The URL of the router that the created dealer socket should CONNECT to.
        :param vk: The Node's VK to connect to. This will be looked up in the overlay network
        """
        url = "tcp://{}:{}".format(ip or vk, ROUTER_DEALER_PORT)
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.add_dealer.__name__,
                                        id=self.verifying_key, url=url, vk=vk)
        self.interface.send_cmd(cmd)

    def add_router(self, ip: str='', vk: str=''):
        """
        Add a router socket at url. Routers are like 'async repliers', and can connect to many Dealer sockets (N-1)
        :param url: The URL the router socket should BIND to
        :param vk: The Node's VK to connect to. This will be looked up in the overlay network
        """
        url = "tcp://{}:{}".format(ip or vk, ROUTER_DEALER_PORT)
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.add_router.__name__, url=url)
        self.interface.send_cmd(cmd)

    def send_request_msg(self, message: MessageBase, timeout=0, ip: str='', vk: str=''):
        """
        TODO docstring
        """
        self.send_request_env(ip=ip, vk=vk, envelope=self._package_msg(message), timeout=timeout)

    def send_request_env(self, envelope: Envelope, timeout=0, ip: str='', vk: str=''):
        url = "tcp://{}:{}".format(ip or vk, ROUTER_DEALER_PORT)
        reply_uuid = EnvelopeAuth.reply_uuid(envelope.meta.uuid)

        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.request.__name__, url=url,
                                        envelope=envelope, timeout=timeout, reply_uuid=reply_uuid)
        self.interface.send_cmd(cmd)

    def send_reply(self, message: MessageBase, request_envelope: Envelope):
        """
        Send a reply message (via a Router socket) for the original reqeust in request_envelope (which came from a
        Dealer socket). Replies envelope are created as a deterministic function of their original request envelope,
        so that both parties (the sender and receiver) are in agreement on what the reply envelope should look like
        :param message: A MessageBase instance that denotes the reply data
        :param request_envelope: An Envelope instance that denotes the envelope of the original request that we are
        replying to
        """
        requester_id = request_envelope.seal.verifying_key
        reply_env = self._package_reply(reply=message, req_env=request_envelope)
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.reply.__name__,
                                        id=requester_id, envelope=reply_env)
        self.interface.send_cmd(cmd)

    def teardown(self):
        """
        Teardown the entire application stack
        """
        self.log.important("Composer tearing down application!")
        self.interface.teardown()

