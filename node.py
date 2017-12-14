import time

import zmq
from zmq.asyncio import Context, Poller
import asyncio

# types of envelopes:
# transactions
# blocks to sign
# hashproofs

# transactions can come at anytime
# blocks are comprised every 1 second or 10,000 transactions
# blocks are hashed and the hash is signed by all parties
# the bundle of signatures is hashed and compared
# if all is well, the block is added to the database

async def transaction_box():
	pass

async def block_box():
	pass

async def hash_box():
	pass

asyncio.get_event_loop().run_until_complete(asyncio.wait([
    transaction_box(),
    block_box(),
    hash_box(),
]))