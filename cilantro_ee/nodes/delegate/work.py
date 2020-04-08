import hashlib
from cilantro_ee.crypto.transaction import transaction_is_valid, TransactionException
from cilantro_ee.crypto.wallet import _verify
import asyncio
import time




async def gather_transaction_batches(queue, expected_batches, timeout=5):
    # Wait until the queue is filled before starting timeout
    while len(queue) == 0:
        await asyncio.sleep(0)

    # Now wait until the rest come in or the timeout is triggered
    start = time.time()
    while len(queue) < expected_batches or time.time() - start < timeout:
        await asyncio.sleep(0)

