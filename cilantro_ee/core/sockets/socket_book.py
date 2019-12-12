from cilantro_ee.services.overlay.sync_client import OverlayClientSync
from cilantro_ee.core.sockets.services import SocketStruct, get, Protocols
import asyncio
import zmq.asyncio
import json

# Keeps a dictionary between a VK and an IP string
# Use refresh() to fetch any new VKs to stay up to date
# You must turn the IP strings into SocketStructs yourself.
# this is currently available only for tcp connections


class SocketBook:
    def __init__(self, peer_service_address: SocketStruct, port: int, ctx: zmq.asyncio.Context, phonebook_function: callable=None):
        # self.port = port
        self.peer_service_address = peer_service_address
        self.phonebook_function = phonebook_function
        self.sockets = {}
        self.port = port
        self.ctx = ctx

    async def refresh(self):
        pb_nodes = set(self.phonebook_function())
        current_nodes = set(self.sockets.keys())

        # Delete / remove old nodes
        to_del = self.old_nodes(pb_nodes, current_nodes)

        for node in to_del:
            self.remove_node(node)

        # Add new nodes
        to_add = self.new_nodes(pb_nodes, current_nodes)

        coroutines = [self.find_node(m) for m in to_add]

        tasks = asyncio.gather(*coroutines)
        loop = asyncio.get_event_loop()

        if loop.is_running():
            results = await asyncio.ensure_future(tasks)
        else:
            results = loop.run_until_complete(tasks)

        for r in results:
            if r is not None:
                _r = json.loads(r)

                vk, tcp_str = [(k, v) for k, v in _r.items()][0]

                self.sockets.update({vk: SocketStruct(protocol=Protocols.TCP, id=tcp_str, port=self.port)})

    async def find_node(self, node):
        find_message = ['find', node]
        find_message = json.dumps(find_message).encode()

        return await get(self.peer_service_address, msg=find_message, ctx=self.ctx, timeout=1000)

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
