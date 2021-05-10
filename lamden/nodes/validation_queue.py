import asyncio
import math
from lamden.logger.base import get_logger

class ValidationQueue:
    def __init__(self, consensus_percent, get_all_peers, process_new_block, wallet):

        self.log = get_logger("VALIDATION QUEUE")

        self.needs_validation_queue = []
        self.validation_results = {}

        self.consensus_percent = consensus_percent
        self.get_all_peers = get_all_peers
        self.process_new_block = process_new_block
        self.wallet = wallet

    def append(self, processing_results):
        self.log.debug("ADDING TO NEEDS VALIDATION QUEUE")

        tx = processing_results['tx']
        results = processing_results['results']

        self.add_solution(
            hlc_timestamp=tx['hlc_timestamp'],
            node_vk=self.wallet.verifying_key,
            msg=results[0]
        )
        self.needs_validation_queue.append(tx['hlc_timestamp'])

    def awaiting_validation(self, hlc_timestamp):
        return hlc_timestamp in self.needs_validation_queue

    def is_duplicate(self, hlc_timestamp, node_vk):
        try:
            return self.validation_results[hlc_timestamp]['delegate_solutions'][node_vk]
        except KeyError:
            return False

    def add_solution(self, hlc_timestamp, node_vk, results):
        # Store data about the tx so it can be processed for consensus later.
        if hlc_timestamp not in self.validation_results:
            self.validation_results[hlc_timestamp] = {}
            self.validation_results[hlc_timestamp]['delegate_solutions'] = {}

        self.validation_results[hlc_timestamp]['delegate_solutions'][node_vk] = results

        # self.log.debug(self.validation_results[hlc_timestamp]['delegate_solutions'])

    async def process_next(self):
        self.needs_validation_queue.sort()
        next_hlc_timestamp = self.needs_validation_queue[0]

        transaction_info = self.validation_results[next_hlc_timestamp]

        consensus_info = await self.check_consensus(transaction_info)

        if consensus_info['has_consensus']:
            # remove the hlc_timestamp from the needs validation queue to prevent reprocessing
            try:
                self.needs_validation_queue.remove(next_hlc_timestamp)
            except ValueError:
                self.log.error(f'{next_hlc_timestamp} was processed for consensus but did not exist in needs_validation queue!')

            self.log.info(f'{next_hlc_timestamp} HAS A CONSENSUS OF {consensus_info["solution"]}')

            if consensus_info['matches_me']:
                self.log.debug('I AM IN THE CONSENSUS')
                # I'm in consensus so I can use my results
                results = transaction_info['delegate_solutions'][self.wallet.verifying_key]

            else:
                self.log.error(f'There was consensus on {next_hlc_timestamp} but I\'m NOT IN CONSENSUS')
                # TODO What to do if the node wasn't in the consensus group?

                # Get the actual solution result
                for delegate in transaction_info['delegate_solutions']:
                    if transaction_info['delegate_solutions'][delegate]['merkle_tree']['leaves'] == consensus_info['solution']:
                        results = transaction_info['delegate_solutions'][delegate]
                        # TODO Do something with the actual consensus solution
                        break

            self.process_new_block(results)

    async def check_consensus(self, transaction_info):
        # Get the number of current delegates
        num_of_peers = len(self.get_all_peers())

        # TODO How to set consensus percentage?
        # Cal the number of current delagates that need to agree
        consensus_needed = math.ceil(num_of_peers * (self.consensus_percent / 100))

        # Get the current solutions
        delegate_solutions = transaction_info['delegate_solutions']
        total_solutions = len(delegate_solutions)

        # Return if we don't have enough responses to attempt a consensus check
        if (total_solutions < consensus_needed):
            return {
                'has_consensus': False,
                'consensus_needed': consensus_needed,
                'total_solutions': total_solutions
            }

        solutions = {}
        for delegate in delegate_solutions:
            solution = delegate_solutions[delegate]['merkle_tree']['leaves'][0]

            if solution not in solutions:
                solutions[solution] = 1
            else:
                solutions[solution] += 1

        for solution in solutions:
            # if one solution has enough matches to put it over the consensus_needed
            # then we have consensus for this solution
            if solutions[solution] > consensus_needed:
                my_solution = delegate_solutions[self.wallet.verifying_key]['merkle_tree']['leaves'][0]
                return {
                    'has_consensus': True,
                    'consensus_needed': consensus_needed,
                    'solution': solution,
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
