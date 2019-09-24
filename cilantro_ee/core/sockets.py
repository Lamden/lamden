from cilantro_ee.protocol.overlay.network import Network
from cilantro_ee.storage.vkbook import PhoneBook
import asyncio


class MasternodeSockets:
    def __init__(self, network: Network):
        # Mapping between VK and ZMQ socket
        self.network = network
        self.sockets = {}

    async def refresh(self):
        pass

    @staticmethod
    def new_nodes(phone_book_nodes, current_nodes):
        return phone_book_nodes - current_nodes

    @staticmethod
    def old_nodes(phone_book_nodes, current_nodes):
        return current_nodes - phone_book_nodes

