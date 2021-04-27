import asyncio
from copy import deepcopy
import time
from lamden.logger.base import get_logger
from lamden import router, storage
from lamden.crypto.wallet import verify
from lamden.crypto import transaction
from contracting.client import ContractingClient

class WorkValidator(router.Processor):
    def __init__(self, hlc_clock, wallet, add_to_queue, get_masters, client: ContractingClient, nonces: storage.NonceStorage, debug=True, expired_batch=5,
                 tx_timeout=5):

        self.tx_expiry_sec = 1

        self.log = get_logger('Work Inbox')
        self.log.propagate = debug

        self.masters = []
        self.tx_timeout = tx_timeout

        self.nonces = nonces
        self.client = client

        self.add_to_queue = add_to_queue
        self.get_masters = get_masters

        self.wallet = wallet
        self.hlc_clock = hlc_clock


    async def process_message(self, msg):
        self.log.info(f'Received work from {msg["sender"][:8]}')
        self.log.info(msg)

        self.log.info({'sender': msg["sender"], 'me': self.wallet.verifying_key })

        if msg["sender"] == self.wallet.verifying_key:
            return

        self.masters = self.get_masters()

        self.log.info({'masters': self.masters})

        if msg['sender'] not in self.masters:
            self.log.error(f'TX Batch received from non-master {msg["sender"][:8]}')
            return

        if not verify(vk=msg['sender'], msg=msg['input_hash'], signature=msg['signature']):
            self.log.error(f'Invalidly signed TX received from master {msg["sender"][:8]}')

        self.log.debug("Checking Expired")
        await self.check_expired(msg['hlc_timestamp'])
        self.log.debug("Done Checking Expired")
        '''
        if await self.check_expired(msg['hlc_timestamp']):
            self.log.error(f'Expired TX from master {msg["sender"][:8]}')
            return
        '''

        transaction.transaction_is_valid(
            transaction=msg['tx'],
            expected_processor=msg['sender'],
            client=self.client,
            nonces=self.nonces,
            strict=False
        )

        await self.hlc_clock.merge_hlc_timestamp(msg['hlc_timestamp'])
        await self.add_to_queue(msg)

        self.log.info(f'Received new work from {msg["sender"][:8]} to my queue.')


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
