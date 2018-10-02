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
        self.network = Network(vk=Auth.vk, storage=None)
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
        await self.discover()
        self.log.important('''
###########################################################################
#   DISCOVERY COMPLETE
###########################################################################
        ''')
        await self.bootstrap()
        self.log.important('''
###########################################################################
#   BOOTSTRAP COMPLETE
###########################################################################
        ''')
        await self.authorize()
        self.log.important('''
###########################################################################
#   HANDSHAKE COMPLETE
###########################################################################
        ''')

    async def discover(self):
        await Discovery.discover_nodes(Discovery.host_ip)

    async def bootstrap(self):
        addrs = [(Discovery.discovered_nodes[vk], self.network.port) \
            for vk in Discovery.discovered_nodes]
        while True:
            if len(addrs) == 1 and Auth.vk not in VKBook.get_masternodes():
                self.log.critical('''
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
x   BOOTSTRAP FAILED: Cannot find other nodes and also not a masternode
x       Retrying...
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
                ''')
                await self.discover()
            else:
                break

        await self.network.bootstrap(addrs)

    async def authorize(self):
        self.log.critical(self.neighbors)
        # await asyncio.gather(*[
        #     Handshake.initiate_handshake() for neighbor in self.neighbors
        # ])

        await asyncio.sleep(1)

    async def lookup_vks(self):
        pass
