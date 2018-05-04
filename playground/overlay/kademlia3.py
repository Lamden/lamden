import asyncio
from kademlia.network import Server
from cilantro.logger import get_logger

log = get_logger("NODE3")
name = "NODE_3"

PORT = 7780
OTHER_PORTS = [5580, 6680]
# OTHER_PORTS = [5580] # omit node 2
HOST_URL = '127.0.0.1'

loop = asyncio.get_event_loop()
node = Server(node_id=name)
node.listen(PORT)

# Bootstrap this node on others
boots = []
for port in OTHER_PORTS + [PORT]:
    boots.append((HOST_URL, port))

log.critical("bootstrapping node..")
loop.run_until_complete(node.bootstrap(boots))
log.critical("bootstrap done.")

log.critical("getting my-key...")
result = loop.run_until_complete(node.get("my-key"))
log.critical("got result: {}".format(result))

log.critical("running forever")
loop.run_forever()