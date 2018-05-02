import asyncio
from kademlia.network import Server

PORT = 5580
HOST_URL = '127.0.0.1'

loop = asyncio.get_event_loop()
node = Server()
node.listen(PORT)

# Bootstrap this node on itself
loop.run_until_complete(node.bootstrap([(HOST_URL, PORT)]))

loop.run_forever()