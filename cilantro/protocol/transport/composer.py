from cilantro import Constants
from cilantro.messages import MessageBase, ReactorCommand, Envelope
from cilantro.protocol.reactor.interface import ReactorInterface
from cilantro.protocol.reactor.executor import *

import zmq.asyncio
"""
TODO docstring
"""


class Composer:

    def __init__(self, interface: ReactorInterface, signing_key: str):
        super().__init__()
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

    def _package_reply(self, reply: MessageBase, request_envelope: Envelope) -> Envelope:
        """
        Convenience method to create a reply envelope. The difference between this func and _package_msg, is that
        in the reply envelope the UUID must be the hash of the original request's uuid (not some randomly generated int)
        :param reply: The reply message (an instance of MessageBase)
        :param request_envelope: The original request envelope (an instance of Envelope)
        :return: An Envelope instance
        """
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
        Starts subscribing to 'url'.
        Requires kwargs 'url' of subscriber (IP to sub to as a string), and 'filter', the filter to use subscribe under
        (as a string)
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_sub.__name__, url=url, filter=filter)
        self.interface.send_cmd(cmd)

    def remove_sub(self, url: str, filter: str):
        """
        Remove subscriber at 'url' with filter 'filter'.
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.remove_sub.__name__, url=url,
                                        filter=filter)
        self.interface.send_cmd(cmd)

    def send_pub_msg(self, filter: str, message: MessageBase):
        """
        Publish data with filter frame 'filter'. If data is an envelope, this envelope will be passed sent to the
        ReactorDaemon. If data is a MessageBase, An envelope (including a seal and the metadata) will be created from
        the MessageBase.
        :param filter: A string to use as the filter frame
        :param message: A MessageBase subclass
        """
        self.send_pub_env(filter=filter, envelope=self._package_msg(message))

    def send_pub_env(self, filter: str, envelope: Envelope):
        """
        Publish data with filter frame 'filter'. If data is an envelope, this envelope will be passed sent to the
        ReactorDaemon. If data is a MessageBase, An envelope (including a seal and the metadata) will be created from
        the MessageBase.
        :param filter: A string to use as the filter frame
        :param envelope: An instance of Envelope, or subclass of MessageBase.
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__, filter=filter,
                                        envelope=envelope)
        self.interface.send_cmd(cmd)

    def add_pub(self, url: str):
        """
        Configure the reactor to publish on 'url'.
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.add_pub.__name__, url=url)
        self.interface.send_cmd(cmd)

    def remove_pub(self, url: str):
        """
        Close the publishing socket on 'url'
        """
        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.remove_pub.__name__, url=url)
        self.interface.send_cmd(cmd)

    def add_dealer(self, url: str):
        """
        needs 'url', and 'id'
        """
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.add_dealer.__name__,
                                        url=url, id=self.verifying_key)
        self.interface.send_cmd(cmd)

    def add_router(self, url: str):
        """
        needs 'url', 'callback'
        """
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.add_router.__name__, url=url)
        self.interface.send_cmd(cmd)

    def send_request_msg(self, url: str, message: MessageBase, timeout=0):
        """
        'url', 'data', 'timeout' ... must add_dealer first with the url
        Timeout is a int in miliseconds
        """
        self.send_request_env(self._package_msg(message))

    def send_request_env(self, url: str, envelope: Envelope, timeout=0):
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.request.__name__, url=url,
                                        envelope=envelope, timeout=timeout)
        self.interface.send_cmd(cmd)

    def send_reply(self, message: MessageBase, request_envelope: Envelope):
        """
        'url', 'data', and 'id' ... must add_router first with url
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
