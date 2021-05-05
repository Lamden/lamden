import asyncio
import math
from lamden.logger.base import get_logger

class ValidationQueue:
    def __init__(self, consensus_percent, get_all_peers, wallet):

        self.log = get_logger("VALIDATION QUEUE")

        self.needs_validation_queue = []
        self.validation_results = {}

        self.consensus_percent = consensus_percent
        self.get_all_peers = get_all_peers
        self.wallet = wallet

    def append(self, processing_results):
        self.log.debug("ADDING TO NEEDS VALIDATION QUEUE")

        tx = processing_results['tx']
        results = processing_results['results']
        self.add_solution(
            hlc_timestamp=tx['hlc_timestamp'],
            tx=tx,
            results=results
        )
        self.needs_validation_queue.append(tx['hlc_timestamp'])

    def awaiting_validation(self, hlc_timestamp):
        return hlc_timestamp in self.needs_validation_queue

    def is_duplicate(self, hlc_timestamp, node_vk):
        try:
            return self.validation_results[hlc_timestamp]['delegate_solutions'][node_vk]
        except KeyError:
            return False

    def add_solution(self, hlc_timestamp, tx, results):
        # Store data about the tx so it can be processed for consensus later.
        if hlc_timestamp not in self.validation_results:
            self.validation_results[hlc_timestamp] = {}
            self.validation_results[hlc_timestamp]['delegate_solutions'] = {}

        self.validation_results[hlc_timestamp]['delegate_solutions'][tx['signer']] = results
        self.validation_results[hlc_timestamp]['data'] = tx

    async def process_next(self):
        self.needs_validation_queue.sort()

        transaction_info = self.validation_results[self.needs_validation_queue[0]]

        consensus_info = await self.check_consensus(transaction_info)

        if consensus_info['has_consensus']:
            self.log.info(f'{self.needs_validation_queue[0]} HAS A CONSENSUS OF {consensus_info["solution"]}')

            # remove the hlc_timestamp from the needs validation queue to prevent reprocessing
            self.needs_validation_queue.pop(0)

            if consensus_info['matches_me']:
                self.log.debug('I AM IN THE CONSENSUS')
            else:
                # TODO What to do if the node wasn't in the consensus group?

                # Get the actual solution result
                for delegate in transaction_info['delegate_solutions']:
                    if transaction_info['delegate_solutions'][delegate]['merkle_tree']['leaves'] == consensus_info['solution']:
                        results = transaction_info['delegate_solutions'][delegate]
                        # TODO Do something with the actual consensus solution
                        break

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
