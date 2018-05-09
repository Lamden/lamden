import asyncio
from kademlia.network import Server
from cilantro.logger import get_logger

from cilantro.protocol.overlay.server import MPServer

log = get_logger("NODE2")
name = "NODE_2"

PORT = 6680
OTHER_PORTS = [5580]

if __name__== "__main__":
    log.critical("Main Started")

    node = MPServer(boot_nodes=OTHER_PORTS, node_id=name, port=PORT)
    node.set("my-key", "over 9000")