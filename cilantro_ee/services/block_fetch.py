from cilantro_ee.core.sockets import SocketBook
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.core.top import TopBlockManager
from cilantro_ee.protocol.comm.services import get, defer
import asyncio
from collections import Counter
import time


class ConfirmationCounter(Counter):
    def top_item(self):
        return self.most_common()[0][0]

    def top_count(self):
        return self.most_common()[0][1]


class BlockFetcher:
    def __init__(self, top=TopBlockManager()):
        self.masternodes = SocketBook(None, PhoneBook.contract.get_masternodes)
        self.delegates = SocketBook(None, PhoneBook.contract.get_delegates)
        self.top = top

    async def find_missing_block_indexes(self, confirmations=3, timeout=3000):
        await self.masternodes.refresh()
        await self.delegates.refresh()

        responses = ConfirmationCounter()

        futures = []
        # Fire off requests to all nodes on the network
        for master in self.masternodes.sockets.values():
            f = asyncio.ensure_future(self.get_missing_block_index(master))
            futures.append(f)

        for delegate in self.delegates.sockets.values():
            f = asyncio.ensure_future(self.get_missing_block_index(delegate))
            futures.append(f)

        # Iterate through the status of the
        now = time.time()
        while responses.top_count() < confirmations or time.time() - now > timeout:
            await defer()
            for f in futures:
                if f.done():
                    responses.update([f.result()])

        return responses.top_item()

    async def get_missing_block_index(self, socket):
        response = await get(socket_id=socket, msg=b'GET BLOCK INDEX PLS', timeout=3000, retries=0)
        return response

    def fetch_blocks(self, starting_block_number=0):
        pass