from cilantro.protocol.overlay.kademlia.network import Network
from cilantro.protocol.overlay.auth import Auth
from cilantro.protocol.overlay.discovery import Discovery
from cilantro.protocol.overlay.handshake import Handshake
from cilantro.protocol.overlay.event import Event
from cilantro.protocol.overlay.ip import *
from cilantro.protocol.overlay.kademlia.utils import digest
from cilantro.protocol.overlay.ip import get_public_ip
from cilantro.constants.overlay_network import *
from cilantro.logger.base import get_logger
from cilantro.storage.vkbook import VKBook
from cilantro.protocol.overlay.kademlia.node import Node

import asyncio, os, zmq.asyncio, zmq
from os import getenv as env
from enum import Enum, auto

class OverlayInterface:
    started = False
    log = get_logger('OverlayInterface')

    def __init__(self, sk_hex, loop=None, ctx=None):

        self.loop = loop or asyncio.get_event_loop()
        # asyncio.set_event_loop(self.loop)
        self.ctx = ctx or zmq.asyncio.Context()
        # reset_auth_folder should always be False and True has to be at highest level without any processes
        Auth.setup(sk_hex=sk_hex, reset_auth_folder=False)

        self.network = Network(loop=self.loop, node_id=digest(Auth.vk))
        self.discovery = Discovery(Auth.vk, self.ctx)
        Handshake.setup(loop=self.loop, ctx=self.ctx)
        self.tasks = [
            self.discovery.listen(),
            Handshake.listen(),
            self.network.protocol.listen(),
            self.bootup()
        ]

    def start(self):
        self.loop.run_until_complete(asyncio.gather(
            *self.tasks
        ))

    @property
    def neighbors(self):
        return {item[2]: Node(node_id=digest(item[2]), ip=item[0], port=item[1], vk=item[2]) \
            for item in self.network.bootstrappableNeighbors()}

    @property
    def authorized_nodes(self):
        return Handshake.authorized_nodes

    async def bootup(self):
        addrs = await self.discovery.discover_and_connect()
        if addrs:
            await self.network.bootstrap(addrs)
        self.log.success('''
###########################################################################
#   BOOTSTRAP COMPLETE
###########################################################################\
        ''')
        self.started = True
        Event.emit({ 'event': 'service_status', 'status': 'ready' })

    async def authenticate(self, ip, vk, domain='*'):
        return await Handshake.initiate_handshake(ip, vk, domain)

    async def lookup_ip(self, vk):
        return await self.network.lookup_ip(vk)

    def track_new_nodes(self):
        self.network.track_and_inform()

    def teardown(self):
        self.log.important('Shutting Down.')
        for task in self.tasks:
            task.cancel()
        self.started = False
