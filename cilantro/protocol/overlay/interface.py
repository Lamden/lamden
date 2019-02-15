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
import abc
from enum import Enum, auto

class OverlayInterface(abc.ABC):
    def __init__(self):
        pass
        # interface dictionary

    # returns ip address if found else None
    @abc.abstractmethod
    def get_ip_from_vk(self, vk):
        pass

    # returns ip address if found else None
    @abc.abstractmethod
    def get_ip_and_handshake(self, vk, is_first_time):
        pass

    @abc.abstractmethod
    def handshake_with_ip(self, ip):
        pass

    @abc.abstractmethod
    def ping_ip(self, ip, is_first_time):
        pass

    # don't need this probably
    @abc.abstractmethod
    def add_event_handler(self):
        pass

