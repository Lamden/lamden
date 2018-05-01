from cilantro import Constants
from cilantro.messages import MessageBase, ReactorCommand, Envelope
from cilantro.protocol.reactor.interface import ReactorInterface
from cilantro.protocol.reactor.executor import *


"""
TODO docstring
"""


class Composer:

    def __init__(self, interface: ReactorInterface, signing_key: str, sender_id: str):
        super().__init__()
        self.interface = interface
        self.sender_id = sender_id
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

        return Envelope.create_from_message(message=msg, signing_key=self.signing_key, sender_id=self.sender_id,
                                            verifying_key=self.verifying_key)

    def notify_ready(self):
        self.log.critical("NOTIFIY READY")
        # TODO -- implement (add queue of tx, flush on notify ready, pause on notify_pause

    def notify_pause(self):
        self.log.critical("NOTIFY PAUSE")
        # TODO -- implement

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
        ReactorCore. If data is a MessageBase, An envelope (including a seal and the metadata) will be created from
        the MessageBase.
        :param filter: A string to use as the filter frame
        :param message: A MessageBase subclass
        """
        self.send_pub_env(self._package_msg(message))

    def send_pub_env(self, filter: str, envelope: Envelope):
        """
        Publish data with filter frame 'filter'. If data is an envelope, this envelope will be passed sent to the
        ReactorCore. If data is a MessageBase, An envelope (including a seal and the metadata) will be created from
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


    """
    lets see
    we need to know the ID of the sender. This is tricky because its not inside the request_envelope, but rather
    is sent as an entirely different frame. We could assume that the dealer socket id is always their verifying key 
    (is this too long?). And then, we we get a message in, we assert the signature is valid (which proves their vk), 
    and then assert header frame is their vk, confirming the dealer socket id has been set up properly (on the receving
    end that is)
    
    !!! this doesnt work with relaying. But req/reply will never be relayed? only pub/sub will be relayed? or is that 
    sketch.... we should ahve the option to relay any kind of transaction. IF it is not pub/sub, then this guy should
    not even process the request. The state machine shoudl not touch it. The 'relay' operation is done by the router
    slapping its id to the zmq messages address stack
     -- ok so fuck relaying requests ya?
    
    """
    def send_reply(self, url: str, header: str, message: MessageBase, request_envelope: Envelope):
        """
        'url', 'data', and 'id' ... must add_router first with url
        """
        # TODO do this
        # TODO get envelope uuid's hash % UUID SIZE (which is its sender uuid)
        # create convenience fucn for that

        env = self._package_msg(message)
        cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.reply.__name__, url=url,
                                        id=id, envelope=env)
        self.interface.send_cmd(cmd)
