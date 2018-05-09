import asyncio
from kademlia.network import Server
from cilantro.logger import get_logger
from cilantro.utils.test import MPTesterBase

from cilantro.protocol.overlay.server import MPServer

log = get_logger("NODE1")
name = "NODE_1"

PORT = 5580

if __name__== "__main__":
    log.critical("Main Started")

    node = MPServer(boot_nodes=[], node_id=name, port=PORT)


