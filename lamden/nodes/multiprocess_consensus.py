import asyncio
import multiprocessing
from time import time

from lamden.nodes.determine_consensus import DetermineConsensus

from lamden.logger.base import get_logger


class MultiProcessConsensus:
    def __init__(self, consensus_percent, my_wallet, get_peers_for_consensus):
        self.log = get_logger('MultiProcessConsensus')

        self.determine_consensus = DetermineConsensus(
            consensus_percent=consensus_percent,
            my_wallet=my_wallet
        )

        self.get_peers_for_consensus = get_peers_for_consensus

        self.all_consensus_results = {}

        self.running = False


    async def start(self, validation_results):
        self.running = True

        try:
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

        except Exception as err:
            self.log.error(err)
            print(err)
            return {}
        finally:
            self.running = False

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
                    await asyncio.sleep(0.01)

    async def check_all(self, processes):
        tasks = [asyncio.ensure_future(self.check(process_info)) for process_info in processes]
        await asyncio.wait(tasks)

    def run_it(self, results, num_of_peers, child_conn):
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)

        solutions = results.get('solutions')
        last_check_info = results.get('last_check_info')
        consensus_results = self.determine_consensus.check_consensus(
            solutions,
            num_of_peers,
            last_check_info
        )
        child_conn.send(consensus_results)

        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except RuntimeError as e:
            print(e)

    async def wait_for_done(self):
        while self.running:
            await asyncio.sleep(0.5)
