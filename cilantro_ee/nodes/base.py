from cilantro_ee.protocol.utils.socket import SocketUtil
from cilantro_ee.protocol.multiprocessing.context import Context
from cilantro_ee.logger import get_logger
from cilantro_ee.constants.system_config import MAX_BOOT_WAIT
from cilantro_ee.protocol.overlay.server import OverlayServer
from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.storage.vkbook import VKBook

import asyncio
import os
import time
from cilantro_ee.protocol import wallet


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


# How often (in seconds) a node should ping others to check if they are online
PING_RETRY = min(15, len(VKBook.get_all()))


class NodeBase(Context):

    # These constants can be overwritten by subclasses
    # For dev, we require all nodes to be online. IRL this could perhaps be 2/3 node for each role  --davis
    REQ_MNS = len(VKBook.get_masternodes())
    REQ_DELS = len(VKBook.get_delegates())  # - 1      # remove -1 its to test manual dump.
    REQ_WITS = len(VKBook.get_witnesses())

    def __init__(self, ip, signing_key, name='Node'):
        super().__init__(signing_key=signing_key, name=name)
        
        SocketUtil.clear_domain_register()

        self.log = get_logger(name)
        self.ip = ip

        # Variables to track connected nodes when booting
        self.online_mns, self.online_dels, self.online_wits = set(), set(), set()

        # TODO -- race condition, what if server does not start in time and misses some requests
        self.log.info("Starting node components")
        self.start_node()

        self.log.info("Starting overlay service")
        # self.overlay_proc = LProcess(target=OverlayServer, kwargs={'sk': signing_key, 'ctx': self.zmq_ctx})
        # self.overlay_proc.start()  # TODO should we make this proc a daemon?

        self.overlay_server = OverlayServer(sk=signing_key, ctx=self.zmq_ctx)

        self.start()

    def start(self):
        self.overlay_server.start()

    def start_node(self):
        pass

