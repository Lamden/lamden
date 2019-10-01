from cilantro_ee.protocol.overlay.network import Network
import asyncio


class SocketBook:
    def __init__(self, network: Network=None, phonebook_function: callable=None):
        self.network = network
        self.phonebook_function = phonebook_function
        self.sockets = {}

    async def refresh(self):
        pb_nodes = set(self.phonebook_function())
        current_nodes = set(self.sockets.keys())

        # Delete / remove old nodes
        to_del = self.old_nodes(pb_nodes, current_nodes)

        for node in to_del:
            self.remove_node(node)

        # Add new nodes
        to_add = self.new_nodes(pb_nodes, current_nodes)
        coroutines = [self.network.find_node(client_address=self.network.peer_service_address,
                                             vk_to_find=m) for m in to_add]

        tasks = asyncio.gather(*coroutines)
        loop = asyncio.get_event_loop()

        if loop.is_running():
            results = await asyncio.ensure_future(tasks)
        else:
            results = loop.run_until_complete(tasks)

        for r in results:
            if r is not None:
                self.sockets.update(r)

    @staticmethod
    def new_nodes(phone_book_nodes, current_nodes):
        return phone_book_nodes - current_nodes

    @staticmethod
    def old_nodes(phone_book_nodes, current_nodes):
        return current_nodes - phone_book_nodes

    def remove_node(self, vk):
        entry = self.sockets.get(vk)

        if entry is not None:
            #entry.close()
            del self.sockets[vk]

    def get_socket_for_vk(self, vk):
        return self.sockets.get(vk)
