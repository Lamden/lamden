import asyncio
from copy import deepcopy
import time


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
        if task['sender'] in expected_masters:
            expected_masters.remove(task['sender'])

    for missing_master in expected_masters:
        shim = {
            'transactions': [],
            'timestamp': int(time.time()),
            'signature': '0' * 128,
            'input_hash': missing_master,
            'sender': missing_master
        }
        work.append(shim)


def filter_work(work):
    actual_work = [w for w in work if w is not None]
    return sorted(actual_work, key=lambda x: x['sender'])
    # filtered_work = []
    # print(work)
    # for tx_batch in work:
    #     # Filter out None responses
    #     if tx_batch is None:
    #         continue
    #
    #     # Add the rest to a priority queue based on their timestamp
    #     print(filtered_work)
    #     print(tx_batch)
    #     heapq.heappush(filtered_work, (tx_batch['timestamp'], tx_batch))
    #
    # # Actually sorts the heap. This can be rewritten to use heap push pop.
    # w = []
    # for i in range(len(filtered_work)):
    #     w.append(heapq.heappop(filtered_work))
    #
    # return w
