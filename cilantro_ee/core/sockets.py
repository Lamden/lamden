from cilantro_ee.protocol.overlay.network import Network
from cilantro_ee.storage.vkbook import PhoneBook
import asyncio


class MasternodeSockets:
    def __init__(self, network=None):
        # Mapping between VK and ZMQ socket
        self.network = network
        self.sockets = {}

    async def refresh(self):
        pb_nodes = set(PhoneBook.masternodes)
        current_nodes = set(self.sockets.keys())

        to_add = self.new_nodes(pb_nodes, current_nodes)
        to_del = self.old_nodes(pb_nodes, current_nodes)

        for node in to_add:
            pass

        for node in to_del:
            self.remove_node(node)

    @staticmethod
    def new_nodes(phone_book_nodes, current_nodes):
        return phone_book_nodes - current_nodes

    @staticmethod
    def old_nodes(phone_book_nodes, current_nodes):
        return current_nodes - phone_book_nodes

    def remove_node(self, vk):
        entry = self.sockets.get(vk)

        if entry is not None:
            entry.close()
            del self.sockets[vk]
