import asyncio
import time
from copy import deepcopy


async def gather_transaction_batches(queue: dict, expected_batches: int, timeout=5):
    # Wait until the queue is filled before starting timeout
    while len(set(queue.keys())) == 0:
        await asyncio.sleep(0)

    # Now wait until the rest come in or the timeout is triggered
    start = time.time()
    while len(set(queue.keys())) < expected_batches and time.time() - start < timeout:
        await asyncio.sleep(0)

    work = deepcopy(list(queue.values()))
    queue.clear()

    return work
