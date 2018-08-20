from cilantro.messages.base.base import MessageBase
from cilantro.protocol.reactor.executor import ReactorCommand, SubPubExecutor, DealerRouterExecutor
from cilantro.protocol.reactor.manager import ExecutorManager
from cilantro.messages.envelope.envelope import Envelope
from cilantro.logger import get_logger
from cilantro.protocol.structures import EnvelopeAuth
from cilantro.protocol import wallet
from cilantro.constants.ports import PUB_SUB_PORT, ROUTER_DEALER_PORT
from cilantro.protocol.overlay.interface import OverlayInterface

"""
The Composer class serves as a high level API for a StateMachine (application layer) to execute networking commands on
the ReactorDaemon process. It creates
"""


"""
TODO code a turnt decorator to validate args on a lot of these functions. Namely:
- ip XOR vk should be provided. Vk should be valid 64 char hex, IP should be valid IPv4 address
- Port should be valid port int
- protocol should be either 'ipc'/'tcp'

TODO update docstrings

TODO implement functions that remove sockets

TODO implement functionality to use this without a signing key
"""


class Composer:
    def __init__(self, manager: ExecutorManager, signing_key: str, name='Node'):
        super().__init__()
        self.log = get_logger("{}.Composer".format(name))
        self.manager = manager
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

    def _build_url(self, protocol, port, ip='', vk=''):
        assert protocol in ('ipc', 'tcp'), "Got protocol {}, but only tcp and ipc are supported".format(protocol)

        if vk:
            ip = OverlayInterface.ip_for_vk(vk)
        return "{}://{}:{}".format(protocol, ip, port)

    def add_sub(self, filter: str, protocol: str='tcp', port: int=PUB_SUB_PORT, ip: str='', vk: str=''):
        """
        Connects the subscriber socket to listen to 'URL' with filter 'filter'.
        :param url: The URL to CONNECT the sub socket to (ex 'tcp://17.1.3.4:4200')
        :param filter: The filter to subscribe to. Only data published with this filter will be received. Currently,
        only one filter per CONNECT is supported.
        """
        url = self._build_url(protocol=protocol, port=port, ip=ip, vk=vk)
        self.manager.executors['SubPubExecutor'].add_sub(url=url, filter=filter, vk=vk)

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
        raise NotImplementedError("This still needs to be coded up")

    def remove_sub_filter(self, filter: str, ip: str='', vk: str=''):
        """
        Removes a filters from the sub socket. Unlike the remove_sub API, this does not disconnect a URL. It only
        unsubscribes to 'filter
        :param filter: A string to use as the filter frame. This filter will be unsubscribed.
        """
        raise NotImplementedError("This still needs to be coded up")

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
        self.manager.executors['SubPubExecutor'].send_pub(filter=filter, envelope=envelope.serialize())

    def add_pub(self, protocol: str='tcp', port: int=PUB_SUB_PORT, ip: str=''):
        """
        Create a publisher socket that BINDS to 'url'
        :param url: The URL to publish under.
        :param vk: The Node's VK to connect to. This will be looked up in the overlay network
        """
        url = self._build_url(protocol=protocol, port=port, ip=ip, vk='')
        self.manager.executors['SubPubExecutor'].add_pub(url=url)

    def remove_pub(self, ip: str='', vk: str=''):
        """
        Removes a publisher (duh)
        :param url: The URL of the router that the created dealer socket should CONNECT to.
        :param vk: The Node's VK to connect to. This will be looked up in the overlay network
        """
        raise NotImplementedError("This still needs to be coded up")

    def add_dealer(self, id='', protocol: str='tcp', port: int=PUB_SUB_PORT, ip: str='', vk: str=''):
        """
        Add a dealer socket at url. Dealers are like 'async requesters', and can connect to a single Router socket (1-1)
        (side note: A router socket, however, can connect to N dealers)
        'id' socketopt for the dealer socket will be this node's verifying key
        :param url: The URL of the router that the created dealer socket should CONNECT to.
        :param vk: The Node's VK to connect to. This will be looked up in the overlay network
        """
        if not id:
            id = self.verifying_key

        url = self._build_url(protocol=protocol, port=port, ip=ip, vk=vk)
        self.manager.executors['DealerRouterExecutor'].add_dealer(url=url, id=id, vk=vk)

    def add_router(self, protocol: str='tcp', port: int=ROUTER_DEALER_PORT, ip: str=''):
        """
        Add a router socket at url. Routers are like 'async repliers', and can connect to many Dealer sockets (N-1)
        :param url: The URL the router socket should BIND to
        :param vk: The Node's VK to connect to. This will be looked up in the overlay network
        """
        url = self._build_url(protocol=protocol, port=port, ip=ip, vk='')
        self.manager.executors['DealerRouterExecutor'].add_router(url=url)

    def send_request_msg(self, message: MessageBase, timeout=0, protocol: str='tcp', port: int=ROUTER_DEALER_PORT,
                         ip: str='', vk: str=''):
        """
        TODO docstring
        """
        self.send_request_env(ip=ip, vk=vk, envelope=self._package_msg(message), timeout=timeout, protocol=protocol, port=port)

    def send_request_env(self, envelope: Envelope, timeout=0, protocol: str='tcp', port: int=ROUTER_DEALER_PORT,
                         vk: str='', ip: str=''):
        url = self._build_url(protocol=protocol, port=port, ip=ip, vk=vk)
        reply_uuid = EnvelopeAuth.reply_uuid(envelope.meta.uuid)
        self.manager.executors['DealerRouterExecutor'].request(url=url, envelope=envelope.serialize(),
                                                               timeout=timeout, reply_uuid=reply_uuid)

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
        self.manager.executors['DealerRouterExecutor'].reply(id=requester_id, envelope=reply_env.serialize())

    def teardown(self):
        """
        Teardown the entire application stack
        """
        raise NotImplementedError("This still needs to be coded up")

