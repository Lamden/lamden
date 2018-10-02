from cilantro.protocol.overlay.kademlia.network import Network
from cilantro.protocol.overlay.auth import Auth
from cilantro.protocol.overlay.discovery import Discovery
from cilantro.protocol.overlay.handshake import Handshake
from cilantro.protocol.overlay.ip import *
from cilantro.protocol.overlay.kademlia.utils import digest
from cilantro.protocol.overlay.ip import get_public_ip
from cilantro.logger.base import get_logger
import asyncio, os
from enum import Enum, auto

class OverlayInterface:
    def __init__(self, sk_hex):
        self.log = get_logger('OverlayInterface')
        Auth.setup_certs_dirs(sk_hex=sk_hex)
        self.loop = asyncio.get_event_loop()
        self.network = Network(node_id=digest(Auth.vk), storage=None)
        self.loop.run_until_complete(asyncio.gather(
            Discovery.listen(),
            Handshake.listen(),
            self.network.listen(),
            self.run_tasks()
        ))

    @property
    def neighbors(self):
        return self.network.bootstrappableNeighbors()

    @property
    def authorized_nodes(self):
        return Handshake.authorized_nodes

    async def run_tasks(self):
        self.log.debug('''
        ###########################################################################
        #   START DISCOVERY
        ###########################################################################
        ''')
        await self.discover()
        self.log.debug('''
        ###########################################################################
        #   END DISCOVERY
        ###########################################################################
        ''')
        self.log.debug('''
        ###########################################################################
        #   START BOOTSTRAP
        ###########################################################################
        ''')
        await self.bootstrap()
        self.log.debug('''
        ###########################################################################
        #   END BOOTSTRAP
        ###########################################################################
        ''')
        self.log.debug('''
        ###########################################################################
        #   START HANDSHAKE
        ###########################################################################
        ''')
        await self.authorize()
        self.log.debug('''
        ###########################################################################
        #   END HANDSHAKE
        ###########################################################################
        ''')

    async def discover(self):
        await Discovery.discover_nodes(Discovery.host_ip)

    async def bootstrap(self):
        addrs = [(Discovery.discovered_nodes[vk], self.network.port) \
            for vk in Discovery.discovered_nodes]
        if len(addrs) == 1 and Auth.vk not in VKBook.get_masternodes():
            self.log.critical('''\
            xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
              BOOTSTRAP FAILED: Cannot find other nodes and also not a masternode
            xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\
            ''')
        self.log.critical('''\
        xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
          BOOTSTRAP FAILED: Cannot find other nodes and also not a masternode
        xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\
        ''')
        await self.network.bootstrap(addrs)

    async def authorize(self):
        await asyncio.sleep(1)
