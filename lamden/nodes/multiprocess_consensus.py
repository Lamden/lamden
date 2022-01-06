import asyncio
import multiprocessing
from time import time

from lamden.nodes.determine_consensus import DetermineConsensus

from lamden.logger.base import get_logger
from lamden.nodes.queue_base import ProcessingQueue


class MultiProcessConsensus:
    def __init__(self, consensus_percent, my_wallet, get_peers_for_consensus):
        self.log = get_logger('MultiProcessConsensus')

        self.determine_consensus = DetermineConsensus(
            consensus_percent=consensus_percent,
            my_wallet=my_wallet
        )

        self.get_peers_for_consensus = get_peers_for_consensus

        self.all_consensus_results = {}

    async def start(self, validation_results):
        self.all_consensus_results = {}
        processes = []
        num_of_peers = len(self.get_peers_for_consensus())

        for hlc_timestamp in validation_results:
            parent_conn, child_conn = multiprocessing.Pipe()
            results = validation_results[hlc_timestamp]
            p = multiprocessing.Process(
                target=self.run_it,
                args=[results, num_of_peers, child_conn]
            )
            processes.append({
                'parent_conn': parent_conn,
                'child_conn': child_conn,
                'process': p,
                'hlc_timestamp': hlc_timestamp
            })

        for process_info in processes:
            process = process_info.get('process')
            process.start()

        await self.check_all(processes)

        for process_info in processes:
            process = process_info.get('process')
            process.terminate()
            process.join()

        return self.all_consensus_results

    async def check(self, process_info):
        hlc_timestamp = process_info.get('hlc_timestamp')
        parent_conn = process_info.get('parent_conn')

        start_time = time()
        self.all_consensus_results[hlc_timestamp] = None

        done = False
        timeout = False
        while not done and not timeout:
            if parent_conn.poll():
                self.all_consensus_results[hlc_timestamp] = parent_conn.recv()
                done = True
            else:
                if time() - start_time > 0.1:
                    timeout = True
                else:
                    await asyncio.sleep(0)

    async def check_all(self, processes):
        tasks = [asyncio.ensure_future(self.check(process_info)) for process_info in processes]
        await asyncio.wait(tasks)

    def run_it(self, results, num_of_peers, child_conn):
        solutions = results.get('solutions')
        last_check_info = results.get('last_check_info')
        consensus_results = self.determine_consensus.check_consensus(
            solutions,
            num_of_peers,
            last_check_info
        )
        child_conn.send(consensus_results)



'''

import asyncio
import time
import multiprocessing

processes = []
lst = []
wait_times = [4,3,2,1]

def run_it(wait_time, child_conn):
    print(f'{wait_time} started')

    policy = asyncio.get_event_loop_policy()
    policy.set_event_loop(policy.new_event_loop())

    tasks = asyncio.gather(
        asyncio.sleep(wait_time)
    )
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(tasks)
    print(f'done {wait_time}')
    
    child_conn.send(wait_time)
    
for wait_time in wait_times:
    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(target=run_it, args=[wait_time, child_conn])
    processes.append({
        'parent_conn': parent_conn,
        'child_conn': child_conn,
        'process': p,
        'wait_time': wait_time
    })
    
for process_info in processes:
    process = process_info.get('process')
    process.start()

async def check(parent_conn):
    done = False
    while not done:
        if parent_conn.poll():
            res = parent_conn.recv()
            print(f'received {res}')
            lst.append(res)
            done = True
        await asyncio.sleep(0)
            
async def check_all(processes):
    tasks = [asyncio.ensure_future(check(process_info.get('parent_conn'))) for process_info in processes]
    await asyncio.wait(tasks)
    
tasks = asyncio.gather(
    check_all(processes)
)
loop = asyncio.get_event_loop()
loop.run_until_complete(tasks)

print(lst)

'''
