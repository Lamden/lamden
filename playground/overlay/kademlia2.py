import asyncio
from kademlia.network import Server
from cilantro.logger import get_logger

log = get_logger("NODE2")
name = "NODE_2"

PORT = 6680
OTHER_PORTS = [5580]
HOST_URL = '127.0.0.1'

loop = asyncio.get_event_loop()
node = Server(node_id=name)
node.listen(PORT)

# Bootstrap this node on others
boots = []
for port in OTHER_PORTS + [PORT]:
    boots.append((HOST_URL, port))

loop.run_until_complete(node.bootstrap(boots))

loop.run_forever()