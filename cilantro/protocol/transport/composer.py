from cilantro import Constants
from cilantro.messages import MessageBase, ReactorCommand, Envelope
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.reactor.executor import *


class Composer:

    def __init__(self, interface: ReactorInterface, signing_key: str, sender_id: str):
        super().__init__()
        self.interface = interface
        self.signing_key = signing_key
        self.sender_id = sender_id
        self.verifying_key = Constants.Protocol.Wallets.get_vk(self.signing_key)

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

    def pub(self, filter: str, data):
        """
        Publish data with filter frame 'filter'. If data is an envelope, this envelope will be passed sent to the
        ReactorCore. If data is a MessageBase, An envelope (including a seal and the metadata) will be created from
        the MessageBase.
        :param filter: A string to use as the filter frame
        :param data: An instance of Envelope, or subclass of MessageBase.
        """
        if type(data) is Envelope:
            env = data
        else:
            assert issubclass(type(data), MessageBase), "Data for envelope must be an Envelope or MessageBase instance"
            env = Envelope.create_from_message(message=data, signing_key=self.signing_key, sender_id=self.sender_id,
                                               verifying_key=self.verifying_key)

        cmd = ReactorCommand.create_cmd(SubPubExecutor.__name__, SubPubExecutor.send_pub.__name__, filter=filter,
                                        envelope=env)
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

    # TODO -- implement this shit
    # def add_dealer(self, url: str, id):
    #     """
    #     needs 'url', 'callback', and 'id'
    #     """
    #     cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.add_dealer.__name__,
    #                                 url=url, id=id)
    #     self.interface.send_cmd(cmd)
    #
    # def add_router(self, url: str):
    #     """
    #     needs 'url', 'callback'
    #     """
    #     cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.add_router.__name__, url=url)
    #     self.interface.send_cmd(cmd)
    #
    # def request(self, url: str, metadata: MessageMeta, data: MessageBase, timeout=0):
    #     """
    #     'url', 'data', 'timeout' ... must add_dealer first with the url
    #     Timeout is a int in miliseconds
    #     """
    #     cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.request.__name__, url=url,
    #                                 metadata=metadata, data=data, timeout=timeout)
    #     self.interface.send_cmd(cmd)
    #
    # def reply(self, url: str, id: str, metadata: MessageMeta, data: MessageBase):
    #     """
    #     'url', 'data', and 'id' ... must add_router first with url
    #     """
    #     cmd = ReactorCommand.create_cmd(DealerRouterExecutor.__name__, DealerRouterExecutor.reply.__name__, url=url, id=id,
    #                                 metadata=metadata, data=data)
    #     self.interface.send_cmd(cmd)