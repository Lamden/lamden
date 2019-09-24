from cilantro_ee.protocol.overlay.network import Network
from cilantro_ee.storage.vkbook import PhoneBook
import asyncio


class BlockFetcher:
    def __init__(self, network: Network):
        self.network = network
        self.masternode_sockets = {}

    async def resolve_masternodes(self):
        to_resolve = set(PhoneBook.masternodes) - self.masternode_sockets.keys()

        coroutines = [self.network.find_node(client_address=self.network.peer_service_address,
                                             vk_to_find=m) for m in to_resolve]

        tasks = asyncio.gather(*coroutines)
        loop = asyncio.get_event_loop()

        if loop.is_running():
            results = await asyncio.ensure_future(tasks)
        else:
            results = loop.run_until_complete(tasks)

    def update_masternode_set(self):
        # Checks the Phonebook for new masternodes that could have joined versus the sockets that we have stored
        # If there is are new nodes, those are connected to.
        # If there are old nodes, those are removed from the socket set.

        new_nodes = set(PhoneBook.masternodes) - self.masternode_sockets.keys()

        old_nodes = self.masternode_sockets.keys() - set(PhoneBook.masternodes)
        for o in old_nodes:
            try:
                del self.masternode_sockets[o]
            except:
                pass

        return new_nodes


def fetch_blocks(starting_block_number=0):
    pass