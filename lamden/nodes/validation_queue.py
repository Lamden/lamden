import asyncio
import math
import time
import json
from lamden.logger.base import get_logger

class ValidationQueue:
    def __init__(self, consensus_percent, get_peers_for_consensus, create_new_block, set_peers_not_in_consensus, wallet, stop):

        self.log = get_logger("VALIDATION QUEUE")

        self.needs_validation_queue = []
        self.validation_results = {}

        self.consensus_percent = consensus_percent
        self.get_peers_for_consensus = get_peers_for_consensus
        self.set_peers_not_in_consensus = set_peers_not_in_consensus
        self.create_new_block = create_new_block
        self.stop = stop

        self.wallet = wallet

    def append(self, block_info, hlc_timestamp):
        # self.log.debug(f'ADDING {block_info["hash"][:8]} TO NEEDS VALIDATION QUEUE')

        self.add_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=self.wallet.verifying_key,
            block_info=block_info
        )

        self.needs_validation_queue.append(hlc_timestamp)

    def awaiting_validation(self, hlc_timestamp):
        return hlc_timestamp in self.needs_validation_queue

    def is_duplicate(self, hlc_timestamp, node_vk):
        try:
            return self.validation_results[hlc_timestamp]['solutions'][node_vk]
        except KeyError:
            return False

    def add_solution(self, hlc_timestamp, node_vk, block_info):
        # self.log.debug(f'ADDING {node_vk[:8]}\'s BLOCK INFO {block_info["hash"][:8]} TO NEEDS VALIDATION RESULTS STORE')
        # Store data about the tx so it can be processed for consensus later.
        if hlc_timestamp not in self.validation_results:
            self.validation_results[hlc_timestamp] = {}
            self.validation_results[hlc_timestamp]['solutions'] = {}
            self.validation_results[hlc_timestamp]['last_check_info'] = {
                'ideal_consensus_possible': True,
                'eager_consensus_possible': True,
                'num_of_solutions': 0
            }

        self.validation_results[hlc_timestamp]['solutions'][node_vk] = block_info

        # self.log.debug(self.validation_results[hlc_timestamp]['solutions'])

    async def process_next(self):
        self.needs_validation_queue.sort()
        next_hlc_timestamp = self.needs_validation_queue.pop(0)

        if self.should_check_again(hlc_timestamp=next_hlc_timestamp):
            consensus_result = self.check_consensus(hlc_timestamp=next_hlc_timestamp)
            self.log.debug(consensus_result)

            if consensus_result['has_consensus']:
                # self.log.info(f'{next_hlc_timestamp} HAS A CONSENSUS OF {consensus_info["solution"]}')

                self.log.debug(json.dumps({
                    'type': 'tx_lifecycle',
                    'file': 'validation_queue',
                    'event': 'has_consensus',
                    'consensus_info': consensus_result,
                    'hlc_timestamp': next_hlc_timestamp,
                    'system_time': time.time()
                }))

                if consensus_result['matches_me']:
                    # disconnect from peers that aren't in consensus
                    asyncio.ensure_future(self.drop_bad_peers(
                        all_block_results=self.validation_results.pop(next_hlc_timestamp),
                        consensus_result=consensus_result
                    ))

                    # TODO do something with the consensus result?
                    # results = transaction_info['solutions'][self.wallet.verifying_key]

                else:
                    # TODO What to do if the node wasn't in the consensus group?
                    # TODO Run Cathup? How?
                    self.log.error(f'NOT IN CONSENSUS {next_hlc_timestamp} {consensus_result["my_solution"][:12]}. STOPPING NODE')

                    # TODO get the actual consensus solution and do something with it
                    all_block_results = self.validation_results[next_hlc_timestamp]
                    for delegate in all_block_results['solutions']:
                        if all_block_results['solutions'][delegate]['hash'] == consensus_result['solution']:
                            results = all_block_results['solutions'][delegate]
                            # TODO do something with the actual consensus solution
                            break

                    # TODO don't stop node, instead recover somehow
                    self.stop()

                # returning here will ensure the hlc_timestamp doesnt' get added back to the validation queue and as
                # such not reprocessed
                return

        # Add the HLC_timestamp back to the queue to be reprocessed
        # Should only get here if we didn't need to check consensus again or if we did and no consensus was realized
        self.needs_validation_queue.append(next_hlc_timestamp)


    def should_check_again(self, hlc_timestamp):
        # if no new solutions have arrived since last check then don't waste resources checking consensus again
        num_of_solutions = len(self.validation_results[hlc_timestamp]['solutions'])
        if self.validation_results[hlc_timestamp]['last_check_info']['num_of_solutions'] == num_of_solutions:
            return False
        return True

    def check_consensus(self, hlc_timestamp):
        '''
            Consensus situations:
                ideal: one solution meets the consensus needed threshold and no more checking is required
                eager: no one solution meets the consensus threshold. Take the highest result if no other solution could overtake it.
                failure: Consensus is SPLIT, all results are in and the top results are tied. In this case take the numerical hex value that is the highest.
        '''
        solutions = self.validation_results[hlc_timestamp]['solutions']
        # set the number of solutions we are checking this time
        self.validation_results[hlc_timestamp]['last_check_info']['num_of_solutions'] = len(solutions)

        # Get the number of current nodes and add yourself
        num_of_peers = len(self.get_peers_for_consensus()) + 1

        # TODO What should self.consensus_percent be set to?
        # determine the number of matching answers we need to form consensus
        consensus_needed = math.ceil(num_of_peers * (self.consensus_percent / 100))

        # Get the number of current solutions
        total_solutions_received = len(solutions)
        '''
        Return if we don't have enough responses to attempt an ideal consensus check
        Which means consensus on any block solution doesn't start till we have at least enough respondents to get a
            first attempt at ideal consensus
        This COULD mean that block production stalls for a moment if a lot of node go offline.. but I'm not 100% sure
            if that is a real possibility.

        Example:
            num_of_peers = 10 (there are 10 peers currently marked by the network as connected and in_conensus
            consensus_needed = 6 (51% rounded up)
            total_solutions_received = 6 (we can now start checking consensus moving from ideal to eager to
                                          failure as more solutions arrive)
        '''
        if total_solutions_received < consensus_needed:
            # TODO Discuss possible scenario where enough peers go offline that we never reach the consensus number..
            return {
                'has_consensus': False
            }

        my_solution = solutions[self.wallet.verifying_key]['hash']
        solutions_missing = num_of_peers - total_solutions_received
        tally_info = self.tally_solutions(solutions=solutions)

        if self.validation_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible']:
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
                'ideal_consensus_possible': True,
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
                'eager_consensus_possible': True,
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
            results_list.append({
                'solution': solution,
                'consensus_amount': tallies[solution]
            })
        results_list = sorted(results_list, key=lambda x: x['consensus_amount'])

        # Get a list of the top solution(s)
        top_solutions_list = []
        for i in range(len(results_list)):
            if i == 0:
                top_solutions_list.append(results_list[0])
            else:
                if results_list[i]['consensus_amount'] == top_solutions_list[i - 1]['consensus_amount']:
                    top_solutions_list.append(results_list[i])
                else:
                    break

        return {
            'tallies': tallies,
            'results_list': results_list,
            'top_solutions_list': top_solutions_list,
            'is_tied': len(top_solutions_list) > 1
        }

    def drop_bad_peers(self, all_block_results, consensus_result):
        correct_solution = consensus_result['solution']
        out_of_consensus = []
        for node_vk in all_block_results['solutions']:
            if all_block_results['solutions'][node_vk]['hash'] != correct_solution:
                out_of_consensus.append(node_vk)
        self.set_peers_not_in_consensus(out_of_consensus)


    def __len__(self):
        return len(self.needs_validation_queue)

    def __setitem__(self, key, value):
        raise ReferenceError

    def __getitem__(self, item):
        return self.validation_results[item]
