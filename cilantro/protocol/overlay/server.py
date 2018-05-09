"""
TEST CLASS FOR DEBUGING/HACKING ONLY

SHOULD NOT BE USED IN PRODUCTION

REMOVE THIS LATER ONCE OVERLAY NET IS CHILL
"""

import asyncio
from kademlia.network import Server
from cilantro.logger import get_logger
from cilantro.utils.test import MPTesterBase, mp_testable


HOST_URL = '127.0.0.1'


@mp_testable(Server)
class MPServer(MPTesterBase):
    @classmethod
    def build_obj(cls, boot_nodes, node_id, port):
        log = get_logger("NODE BUILDER")
        log.info("Creating node on port {} with id {} and boot_nodes {}".format(port, node_id, boot_nodes))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        node = Server(node_id=node_id)
        node.listen(port)

        boots = []
        for p in boot_nodes + [port]:
            boots.append((HOST_URL, p))
        loop.run_until_complete(node.bootstrap(boots))

        return node, loop


