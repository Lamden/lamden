import asyncio
from copy import deepcopy
import capnp
import os
import time
import heapq
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


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


def pad_work(work: list, expected_masters: list):
    for task in work:
        if task.sender.hex() in expected_masters:
            expected_masters.remove(task.sender.hex())

    for missing_master in expected_masters:
        shim = transaction_capnp.TransactionBatch.new_message(
            transactions=[],
            timestamp=time.time(),
            signature=b'\x00' * 64,
            inputHash=missing_master,
            sender=bytes.fromhex(missing_master)
        )
        work.append(shim)


def filter_work(work):
    filtered_work = []
    for tx_batch in work:
        # Filter out None responses
        if tx_batch is None:
            continue

        # Add the rest to a priority queue based on their timestamp
        heapq.heappush(filtered_work, (tx_batch.timestamp, tx_batch))

    return filtered_work
