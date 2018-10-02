from cilantro.protocol.overlay.kademlia.network import Network
from cilantro.protocol.overlay.auth import Auth
from cilantro.protocol.overlay.discovery import Discovery
from cilantro.protocol.overlay.handshake import Handshake
from cilantro.protocol.overlay.ip import *
from cilantro.protocol.overlay.kademlia.utils import digest
from cilantro.protocol.overlay.ip import get_public_ip
import asyncio, os
from enum import Enum, auto

class OverlayInterface:
    def __init__(self, sk_hex):
        Auth.setup_certs_dirs(sk_hex=sk_hex)
        self.loop = asyncio.get_event_loop()
        self.network = Network(node_id=digest(Auth.vk), storage=None)
        self.loop.run_until_complete(asyncio.gather(
            Discovery.listen(),
            Handshake.listen(),
            self.network.listen(),
            self.run_tasks()
        ))

    async def run_tasks(self):
        await self.discover()
        await self.bootstrap()
        await self.authorize()

    async def discover(self):
        await Discovery.discover_nodes(Discovery.host_ip)

    async def bootstrap(self):
        addrs = [(Discovery.discovered_nodes[vk], self.network.port) \
            for vk in Discovery.discovered_nodes]
        await self.network.bootstrap(addrs)

    async def authorize(self):
        await asyncio.sleep(1)
