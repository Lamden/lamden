from cilantro_ee.protocol.utils.socket import SocketUtil
from cilantro_ee.protocol.multiprocessing.context import Context
from cilantro_ee.logger import get_logger
from cilantro_ee.protocol.overlay.server import OverlayServer
from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.storage.vkbook import VKBook

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
            return vk in VKBook.get_masternodes()
        if group == cls.WITNESS:
            return vk in VKBook.get_witnesses()
        if group == cls.DELEGATE:
            return vk in VKBook.get_delegates()


class NodeBase(Context):

    def __init__(self, ip, signing_key, name='Node'):
        super().__init__(signing_key=signing_key, name=name)
        
        SocketUtil.clear_domain_register()

        self.log = get_logger(name)
        self.ip = ip

        self.log.info("Starting node components")
        self.start_node()
        time.sleep(4)

        self.log.info("Starting overlay service")
        self.overlay_server = OverlayServer(sk=signing_key, ctx=self.zmq_ctx)
        self.start()

    def start(self):
        self.overlay_server.start()

    def start_node(self):
        pass

