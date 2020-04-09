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

    work = []
    while len(queue) > 0:
        work.append(queue.pop(0))
    return work

# # Wait for work from all masternodes that are currently online
#         start = None
#         timeout_timer = False
#         self.log.info(f'{set(self.work.keys())} / {len(set(self.parameters.get_masternode_vks()))} work bags received')
#         while len(set(self.parameters.get_masternode_vks()) - set(self.work.keys())) > 0:
#             await asyncio.sleep(0)
#
#             if len(set(self.work.keys())) > 0 and not timeout_timer:
#                 # Got one, start the timeout timer
#                 timeout_timer = True
#                 start = time.time()
#
#             if timeout_timer:
#                 now = time.time()
#                 if now - start > seconds_to_timeout:
#                     self.log.error('TIMEOUT')
#                     break
#
#         returned_work = deepcopy(list(self.work.values()))
#         self.work.clear()
#
#         return returned_work