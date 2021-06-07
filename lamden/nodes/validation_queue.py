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

    def append(self, block_info, hlc_timestamp):
        self.log.debug(f'ADDING {block_info["hash"][:8]} TO NEEDS VALIDATION QUEUE')
        '''
        self.add_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=self.wallet.verifying_key,
            block_info=block_info
        )
        '''
        self.needs_validation_queue.append(hlc_timestamp)

    def awaiting_validation(self, hlc_timestamp):
        return hlc_timestamp in self.needs_validation_queue

    def is_duplicate(self, hlc_timestamp, node_vk):
        try:
            return self.validation_results[hlc_timestamp]['solutions'][node_vk]
        except KeyError:
            return False

    def add_solution(self, hlc_timestamp, node_vk, block_info):
        self.log.debug(f'ADDING {node_vk[:8]}\'s BLOCK INFO {block_info["hash"][:8]} TO NEEDS VALIDATION RESULTS STORE')
        # Store data about the tx so it can be processed for consensus later.
        if hlc_timestamp not in self.validation_results:
            self.validation_results[hlc_timestamp] = {}
            self.validation_results[hlc_timestamp]['solutions'] = {}
            self.validation_results[hlc_timestamp]['last_result'] = {
                'ideal_consensus_possible': True,
                'eager_consensus_possible': True
            }

        self.validation_results[hlc_timestamp]['solutions'][node_vk] = block_info

        # self.log.debug(self.validation_results[hlc_timestamp]['solutions'])

    async def process_next(self):
        self.needs_validation_queue.sort()
        next_hlc_timestamp = self.needs_validation_queue.pop(0)

        consensus_info = self.check_consensus(hlc_timestamp=next_hlc_timestamp)

        if consensus_info['has_consensus']:
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
                # cleanup validation results
                self.validation_results.pop(next_hlc_timestamp)

                # TODO do something with the consensus result?
                # results = transaction_info['solutions'][self.wallet.verifying_key]

            else:
                # TODO What to do if the node wasn't in the consensus group?
                # TODO Run Cathup? How?
                self.log.error(f'NOT IN CONSENSUS {next_hlc_timestamp} {consensus_info["my_solution"][:12]}. STOPPING NODE')

                # TODO get the actual consensus solution and do something with it
                all_block_results = self.validation_results[next_hlc_timestamp]
                for delegate in all_block_results['solutions']:
                    if all_block_results['solutions'][delegate]['hash'] == consensus_info['solution']:
                        results = all_block_results['solutions'][delegate]
                        # TODO do something with the actual consensus solution
                        break

                # TODO don't stop node, instead recover somehow
                self.stop()
        else:
            # Add the HLC_timestamp back to the queue to be reprocessed
            self.needs_validation_queue.append(next_hlc_timestamp)

    def check_consensus(self, hlc_timestamp):
        '''
            Consensus situations:
                ideal: one solution meets the consensus needed threshold and no more checking is required
                eager: no one solution meets the consensus threshold. Take the highest result if no other solution could overtake it.
                failure: Consensus is SPLIT, all results are in and the top results are tied. In this case take the numerical hex value that is the highest.
        '''
        solutions = self.validation_results[hlc_timestamp]['solutions']

        # Get the number of current nodes and add yourself
        num_of_peers = len(self.get_all_peers()) + 1

        # TODO How to set consensus percentage?
        # Cal the number of current delagates that need to agree
        consensus_needed = math.ceil(num_of_peers * (self.consensus_percent / 100))

        # Get the current solutions
        total_solutions_received = len(solutions)

        # Return if we don't have enough responses to attempt an ideal consensus check
        if total_solutions_received < consensus_needed:
            # TODO Discuss possible senario where enough peers go offline that we never reach the consensus number.
            # TODO possible this doesn't happen because "self.get_all_peers()" will return the current number of peers
            # TODO every loop and should eventually bring the consensus needed below the recived solutions amount.
            return {'has_consensus': False}

        my_solution = solutions[self.wallet.verifying_key]['hash']
        solutions_missing = num_of_peers - total_solutions_received
        tally_info = self.tally_solutions(solutions=solutions)

        if (self.validation_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible']):
            # Check ideal situation
            ideal_consensus_results = self.check_ideal_consensus(
                tally_info=tally_info,
                my_solution=my_solution,
                consensus_needed=consensus_needed,
                solutions_missing=solutions_missing
            )

            self.validation_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible'] = ideal_consensus_results['ideal_consensus_possible']

            # Return if we found ideal consensus on a solution
            # or there are still enough respondents left that ideal consensus is possible
            if ideal_consensus_results['has_consensus'] or ideal_consensus_results['ideal_consensus_possible']:
                return ideal_consensus_results

        if (self.validation_results[hlc_timestamp]['last_check_info']['eager_consensus_possible']):
            # Check eager situation
            eager_consensus_results = self.check_eager_consensus(
                tally_info=tally_info,
                my_solution=my_solution,
                consensus_needed=consensus_needed,
                solutions_missing=solutions_missing
            )
            self.validation_results[hlc_timestamp]['last_check_info']['eager_consensus_possible'] = eager_consensus_results['eager_consensus_possible']

            # Return if we found eager consensus on a solution
            # or there are still enough respondents left that eager consensus is possible
            if eager_consensus_results['has_consensus'] or eager_consensus_results['eager_consensus_possible']:
                return eager_consensus_results

            # Return Failed situation if ideal and eager consensus is not possible
            # This should always return a consensus result
            return self.check_failed_consensus(
                tally_info=tally_info,
                solutions=solutions,
                consensus_needed=consensus_needed
            )

    def check_ideal_consensus(self, tally_info, my_solution, solutions_missing, consensus_needed):
        top_solution = tally_info['results_list'][0]
        if top_solution['consensus_amount'] > consensus_needed:
            return {
                'has_consensus': True,
                'consensus_needed': consensus_needed,
                'solution': top_solution['solution'],
                'my_solution': my_solution,
                'matches_me': my_solution == top_solution['solution']
            }

        # Check if ideal consensus is mathematically possible
        if top_solution['consensus_amount'] + solutions_missing >= consensus_needed:
            return {
                'has_consensus': False,
                'ideal_consensus_possible': True
            }

        return {
            'has_consensus': False,
            'ideal_consensus_possible': False
        }

    def check_eager_consensus(self, tally_info, my_solution, solutions_missing, consensus_needed):
        # if consensus is tied and there are not more expected solutions then eager consensus is not possible
        if tally_info['is_tied'] and solutions_missing == 0:
            return {
                'has_consensus': False,
                'eager_consensus_possible': False
            }

        # if the winning solution is more than the next best + any new possible solutions then we have eager consensus
        if tally_info['results_list'][0]['consensus_amount'] > tally_info['results_list'][1]['consensus_amount'] + solutions_missing:
            return {
                'has_consensus': True,
                'consensus_needed': consensus_needed,
                'solution': tally_info['results_list'][0]['solution'],
                'my_solution': my_solution,
                'matches_me': my_solution == tally_info['results_list'][0]['solution']
            }

    def check_failed_consensus(self, tally_info, my_solution, consensus_needed):
        for i in range(len(tally_info['top_solutions_list'])):
            tally_info['top_solutions_list'][i]['int'] = int(tally_info['top_solutions_list'][i]['solution'], 16)

        tally_info['top_solutions_list'] = sorted(tally_info['top_solutions_list'], key=lambda x: x.int)

        return {
            'has_consensus': True,
            'consensus_needed': consensus_needed,
            'solution': tally_info['top_solutions_list'][0]['solution'],
            'my_solution': my_solution,
            'matches_me': my_solution == tally_info['top_solutions_list'][0]['solution'],
        }


    def tally_solutions(self, solutions):
        tallies = {}

        # Tally up matching solutions
        for node in solutions:
            solution = solutions[node]['hash']

            if solution not in tallies:
                tallies[solution] = 1
            else:
                tallies[solution] += 1

        # Sort the Tally object into a list of result objects
        results_list = []
        for solution in tallies:
            results_list.push({
                'solution': solution,
                'consensus_amount': tallies[solution]
            })
        results_list = sorted(results_list, key=lambda x: x.consensus_amount)

        # Get a list of the top solution(s)
        top_solutions_list = []
        for i in range(len(results_list)):
            if i == 0:
                top_solutions_list.push(results_list[0])
            else:
                if results_list[i]['consensus_amount'] == top_solutions_list[i - 1]['consensus_amount']:
                    top_solutions_list.push(results_list[i])
                else:
                    break

        return {
            'tallies': tallies,
            'results_list': results_list,
            'top_solutions_list': top_solutions_list,
            'is_tied': len(top_solutions_list) > 1
        }

    def __len__(self):
        return len(self.needs_validation_queue)

    def __setitem__(self, key, value):
        raise ReferenceError

    def __getitem__(self, item):
        return self.validation_results[item]
