from cilantro.protocol.multiprocessing.context import Context
from cilantro.logger import get_logger
from cilantro.constants.system_config import MAX_BOOT_WAIT
from cilantro.protocol.overlay.kademlia.auth import Auth
from cilantro.protocol.overlay.server import OverlayServer
from cilantro.utils.lprocess import LProcess
from cilantro.storage.vkbook import VKBook

import asyncio
import os
import time
from cilantro.protocol import wallet


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

        self.log.info("Starting overlay service")
        self.overlay_proc = LProcess(target=OverlayServer, kwargs={'sk': signing_key})
        self.overlay_proc.start()  # TODO should we make this proc a daemon?

        self.log.notice("Node with vk {} has ip {}".format(self.verifying_key, ip))
        # self.add_overlay_handler_fn('node_offline', self._node_offline_event)
        # self.add_overlay_handler_fn('node_online', self._node_online_event)

        # self._wait_for_nodes()

        self.start()

    def start(self):
        pass

