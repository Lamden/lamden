from cilantro_ee.core.sockets.socket import SocketUtil
from cilantro_ee.core.utils.context import Context
from cilantro_ee.core.logger import get_logger
from cilantro_ee.services.overlay.server import OverlayServer
from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.services.storage.vkbook import VKBook, PhoneBook
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.constants import conf
import asyncio
import time


class NodeTypes:
    MN = 'mn'
    WITNESS = 'w'
    DELEGATE = 'd'

    _ALL_TYPES = {MN, WITNESS, DELEGATE}

    @classmethod
    def check_vk_in_group(cls, vk: str, group: str):
        assert group in cls._ALL_TYPES, "Group '{}' not a valid node type. Must be in {}".format(group, cls._ALL_TYPES)
        if group == cls.MN:
            return vk in PhoneBook.masternodes
        if group == cls.WITNESS:
            return vk in PhoneBook.witnesses
        if group == cls.DELEGATE:
            return vk in PhoneBook.delegates


class NodeBase(Context):

    def __init__(self, ip, signing_key, name='Node'):
        super().__init__(signing_key=signing_key, name=name)
        
        SocketUtil.clear_domain_register()

        self.log = get_logger(name)
        self.ip = ip
        self.wallet = Wallet(seed=signing_key)

        conf.HOST_VK = self.wallet.verifying_key()

        self.log.info("Starting node components")
        quorum = self.start_node()

        self.log.info("Starting overlay service")
        self.overlay_server = OverlayServer(sk=signing_key, ctx=self.zmq_ctx, quorum=1)
        self.start()

    def start(self):
        self.overlay_server.start()

    def start_node(self):
        pass

