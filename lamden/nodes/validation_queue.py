import asyncio
import math
import time
import json
from lamden.logger.base import get_logger

class ValidationQueue:
    def __init__(self, consensus_percent, get_all_peers, create_new_block, wallet, stop):

        self.log = get_logger("VALIDATION QUEUE")

        self.needs_validation_queue = []
        self.validation_results = {}

        self.consensus_percent = consensus_percent
        self.get_all_peers = get_all_peers
        self.create_new_block = create_new_block
        self.stop = stop

        self.wallet = wallet

    def append(self, processing_results):
        # self.log.debug("ADDING TO NEEDS VALIDATION QUEUE")

        tx = processing_results['tx']
        results = processing_results['results']

        self.add_solution(
            hlc_timestamp=tx['hlc_timestamp'],
            node_vk=self.wallet.verifying_key,
            results=results[0]
        )
        self.needs_validation_queue.append(tx['hlc_timestamp'])

    def awaiting_validation(self, hlc_timestamp):
        return hlc_timestamp in self.needs_validation_queue

    def is_duplicate(self, hlc_timestamp, node_vk):
        try:
            return self.validation_results[hlc_timestamp]['solutions'][node_vk]
        except KeyError:
            return False

    def add_solution(self, hlc_timestamp, node_vk, results):
        # Store data about the tx so it can be processed for consensus later.
        if hlc_timestamp not in self.validation_results:
            self.validation_results[hlc_timestamp] = {}
            self.validation_results[hlc_timestamp]['solutions'] = {}

        self.validation_results[hlc_timestamp]['solutions'][node_vk] = results

        # self.log.debug(self.validation_results[hlc_timestamp]['solutions'])

    async def process_next(self):
        self.needs_validation_queue.sort()
        next_hlc_timestamp = self.needs_validation_queue[0]

        transaction_info = self.validation_results[next_hlc_timestamp]

        consensus_info = self.check_consensus(transaction_info)

        if consensus_info['has_consensus']:
            # remove the hlc_timestamp from the needs validation queue to prevent reprocessing
            try:
                self.needs_validation_queue.remove(next_hlc_timestamp)
            except ValueError:
                self.log.error(f'{next_hlc_timestamp} was processed for consensus but did not exist in needs_validation queue!')

            # self.log.info(f'{next_hlc_timestamp} HAS A CONSENSUS OF {consensus_info["solution"]}')

            self.log.debug(json.dumps({
                'type': 'tx_lifecycle',
                'file': 'validation_queue',
                'event': 'has_consensus',
                'consensus_info': consensus_info,
                'hlc_timestamp': next_hlc_timestamp,
                'system_time': time.time()
            }))

            if consensus_info['matches_me']:
                # self.log.debug(f'CONSENSUS {next_hlc_timestamp} {consensus_info["solution"][:12]}')

                # I'm in consensus so create new block with my results
                results = transaction_info['solutions'][self.wallet.verifying_key]
                self.create_new_block(results)

            else:
                # self.log.error(f'There was consensus on {next_hlc_timestamp} but I\'m NOT IN CONSENSUS')
                # TODO What to do if the node wasn't in the consensus group?
                self.log.error(f'NOT IN CONSENSUS {next_hlc_timestamp} {consensus_info["my_solution"][:12]}')

                # Get the actual solution result
                for delegate in transaction_info['solutions']:
                    if transaction_info['solutions'][delegate]['merkle_tree']['leaves'] == consensus_info['solution']:
                        results = transaction_info['solutions'][delegate]
                        # TODO Do something with the actual consensus solution
                        break
                self.stop()
                return



    def check_consensus(self, transaction_info):
        # Get the number of current nodes and add yourself
        num_of_peers = len(self.get_all_peers()) + 1

        # TODO How to set consensus percentage?
        # Cal the number of current delagates that need to agree
        consensus_needed = math.ceil(num_of_peers * (self.consensus_percent / 100))

        # Get the current solutions
        solutions = transaction_info['solutions']
        total_solutions = len(solutions)

        # Return if we don't have enough responses to attempt a consensus check
        if (total_solutions < consensus_needed):
            return {
                'has_consensus': False,
                'consensus_needed': consensus_needed,
                'total_solutions': total_solutions
            }

        solution_tracker = {}
        for node in solutions:
            solution = solutions[node]['merkle_tree']['leaves'][0]

            if solution not in solution_tracker:
                solution_tracker[solution] = 1
            else:
                solution_tracker[solution] += 1

        for solution in solution_tracker:
            # if one solution has enough matches to put it over the consensus_needed
            # then we have consensus for this solution
            if solution_tracker[solution] > consensus_needed:
                my_solution = solutions[self.wallet.verifying_key]['merkle_tree']['leaves'][0]
                return {
                    'has_consensus': True,
                    'consensus_needed': consensus_needed,
                    'solution': solution,
                    'my_solution': my_solution,
                    'matches_me': my_solution == solution,
                    'total_solutions': total_solutions
                }

        # If we get here then there was either not enough responses to get consensus or we had a split
        # TODO what if split consensus? Probably very unlikely with a bunch of delegates but could happen
        return {
            'has_consensus': False,
            'consensus_needed': consensus_needed,
            'total_solutions': total_solutions
        }

    def __len__(self):
        return len(self.needs_validation_queue)

    def __setitem__(self, key, value):
        raise ReferenceError

    def __getitem__(self, item):
        return self.validation_results[item]
