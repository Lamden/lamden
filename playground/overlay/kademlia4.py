import asyncio
from kademlia.network import Server
from cilantro.logger import get_logger

log = get_logger("NODE4")
name = "NODE_4"

PORT = 8880
# OTHER_PORTS = [5580, 6680]
OTHER_PORTS = [5580, 6680, 7780] # omit node 1 and 3
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

log.critical("setting new key 'node-4-info' from node_4...")
loop.run_until_complete(node.set("node-4-info", "dank stuff"))
log.critical("done setting.")

log.critical("\n\nFetching node info for node_id = NODE_3")
result = loop.run_until_complete(node.lookup_ip('NODE_3'))
log.critical("got result from lookup: {}".format(result))

log.critical("running forever")
loop.run_forever()