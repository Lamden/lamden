import asyncio
from kademlia.network import Server
from cilantro.logger import get_logger

log = get_logger("NODE1")
name = "NODE_1"

PORT = 5580
HOST_URL = '127.0.0.1'

loop = asyncio.get_event_loop()
node = Server(node_id=name)
node.listen(PORT)

# Bootstrap this node on itself
log.critical("bootstrapping node")
loop.run_until_complete(node.bootstrap([(HOST_URL, PORT)]))

log.critical("done bootstrapping node...setting my-key")
loop.run_until_complete(node.set("my-key", "my awesome value"))

log.critical("running forever")
loop.run_forever()