from cilantro_ee.protocol.overlay.sync_client import OverlayClientSync
import asyncio

# Keeps a dictionary between a VK and an IP string
# Use refresh() to fetch any new VKs to stay up to date
# You must turn the IP strings into SocketStructs yourself.
# This means there is no port information on the strings.


class SocketBook:
    def __init__(self, client: OverlayClientSync, phonebook_function: callable=None):
        self.client = client
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
        coroutines = [self.client.async_get_ip_sync(m) for m in to_add]

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
