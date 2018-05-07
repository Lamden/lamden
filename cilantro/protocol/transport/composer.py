from cilantro import Constants
from cilantro.messages import MessageBase, ReactorCommand, Envelope
from cilantro.protocol.reactor.interface import ReactorInterface
from cilantro.protocol.reactor.executor import *
from cilantro.logger import get_logger

"""
The Composer class serves as a high level API for a StateMachine (application layer) to execute networking commands on
the ReactorDaemon process. It creates
"""


class Composer:
    def __init__(self, interface: ReactorInterface, signing_key: str):
        super().__init__()
        self.log = get_logger("Composer")
        self.interface = interface
        self.signing_key = signing_key
        self.verifying_key = Constants.Protocol.Wallets.get_vk(self.signing_key)
        self.log = get_logger("Composer")

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
        self.log.info("Creating REPLY envelope with msg type {} for request envelope {}".format(type(reply), req_env))
        request_uuid = req_env.meta.uuid
        # TODO -- implement once you write the appropriate factory method on Envelope for creating them with a
        # predetermined uuid
        pass

    def resume(self):
        self.log.info("Resuming ReactorInterface")
        self.interface.notify_resume()

    def pause(self):
        self.log.info("Pausing ReactorInterface")
        self.interface.notify_pause()

    def add_sub(self, url: str, filter: str):
        """
        Connects the subscriber socket to listen to 'URL' with filter 'filter'.
        :param url: The URL to CONNECT the sub socket to (ex 'tcp://17.1.3.4:4200')
        :param filter: The filter to subscribe to. Only data published with this filter will be received. Currently,
        only one filter per CONNECT is supported.
        """

        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=url, filter=filter)
        self.interface.send_cmd(cmd)

    def remove_sub(self, url: str, filter: str):
        """
        Stop subscribing to a URL and filter. Note that all other subscriber connections will drop this filter as well
        (so if there is another URL you are subscribing to with the same filter, that sub will no longer work). The
        pattern at this point is to have a single filter for each 'node type', ie witness/delegate/masternode.

        If you wish to stop subscribing to a URL, but not necessarily a filter, then call this method and pass in an
        empty string to FILTER. For example, a delegate might want to stop subscribing to a particular witness, but not
        all witnesses. (TODO -- test this behavior)
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.remove_sub.__name__, url=url,
                                        filter=filter)
        self.interface.send_cmd(cmd)

    def send_pub_msg(self, filter: str, message: MessageBase):
        """
        Publish data with filter frame 'filter'. An envelope (including a seal and the metadata) will be created from
        the MessageBase. If you want to send an existing envelope, use send_pub_env
        :param filter: A string to use as the filter frame
        :param message: A MessageBase subclass
        """
        self.send_pub_env(filter=filter, envelope=self._package_msg(message))

    def send_pub(self, filter: str, envelope: Envelope):
        """
        Publish envelope with filter frame 'filter'.
        :param filter: A string to use as the filter frame
        :param envelope: An instance of Envelope
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__, filter=filter,
                                        envelope=envelope)
        self.interface.send_cmd(cmd)

    def add_pub(self, url: str):
        """
        Create a publisher socket that BINDS to 'url'
        :param url: The URL to BIND the pub socket to (ex 'tcp://17.1.3.4:4200')
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=url)
        self.interface.send_cmd(cmd)

    def remove_pub(self, url: str):
        """
        TODO docstring
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.remove_pub.__name__, url=url)
        self.interface.send_cmd(cmd)

    def add_dealer(self, url: str):
        """
        Add a dealer socket at url. Dealers are like 'async requesters', and can connect to a single Router socket (1-1)
        'id' socketopt for the dealer socket will be this node's verifying key
        :param url: The URL of the router that the created dealer socket should CONNECT to
        """
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.add_dealer.__name__,
                                        url=url, id=self.verifying_key)
        self.interface.send_cmd(cmd)

    def add_router(self, url: str):
        """
        Add a router socket at url. Routers are like 'async repliers', and can connect to many Dealer sockets (N-1)
        :param url: The URL the router socket should BIND to
        """
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.add_router.__name__, url=url)
        self.interface.send_cmd(cmd)

    def send_request_msg(self, url: str, message: MessageBase, timeout=0):
        """
        TODO docstring
        """
        self.send_request_env(self._package_msg(message))

    def send_request_env(self, url: str, envelope: Envelope, timeout=0):
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.request.__name__, url=url,
                                        envelope=envelope, timeout=timeout)
        self.interface.send_cmd(cmd)

    def send_reply(self, message: MessageBase, request_envelope: Envelope):
        """
        Send a reply message (via a Router socket) for the original reqeust in request_envelope (which came from a
        Dealer socket).
        """
        # TODO do this
        # TODO get envelope uuid's hash % UUID SIZE (which is its sender uuid)
        # create convenience fucn for that

        # request_envelope.seal.verifying_key will be the ID to send...we just need to package an envelope and fix the
        # uuid

        env = self._package_msg(message)
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.reply.__name__, url=url,
                                        id=id, envelope=env)
        self.interface.send_cmd(cmd)
