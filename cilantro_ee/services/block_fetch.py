from cilantro_ee.core.sockets import SocketBook
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.core.top import TopBlockManager
import asyncio


class BlockFetcher:
    def __init__(self, top=TopBlockManager()):
        self.masternodes = SocketBook(None, PhoneBook.masternodes)
        self.delegates = SocketBook(None, PhoneBook.delegates)
        self.top = top

    def fetch_blocks(self, starting_block_number=0):
        pass