import asyncio
import math
import time
import json

from lamden.logger.base import get_logger
from lamden.nodes.queue_base import ProcessingQueue

class ValidationQueue(ProcessingQueue):
    def __init__(self, consensus_percent, get_peers_for_consensus, is_next_block, process_from_consensus_result,
                 set_peers_not_in_consensus, wallet, hard_apply_block, stop_node, rollback, testing=False, debug=False):
        super().__init__()

        self.log = get_logger("VALIDATION QUEUE")

        # The main dict for storing results from other nodes
        self.validation_results = {}

        # Store confirmed solutions that I haven't got to yet
        self.last_hlc_in_consensus = ""

        self.consensus_percent = consensus_percent
        self.get_peers_for_consensus = get_peers_for_consensus
        self.set_peers_not_in_consensus = set_peers_not_in_consensus
        self.hard_apply_block = hard_apply_block
        self.process_from_consensus_result = process_from_consensus_result
        self.is_next_block = is_next_block
        self.rollback = rollback
        self.stop_node = stop_node

        self.wallet = wallet

        # For debugging
        self.testing = testing
        self.debug = debug
        self.validation_results_history = {}
        self.detected_rollback = False

    def append(self, block_info, node_vk, hlc_timestamp, transaction_processed=None):
        # self.log.debug(f'ADDING {block_info["hash"][:8]} TO NEEDS VALIDATION QUEUE')

        # don't accept this solution if it's for an hlc_timestamp we already had consensus on
        if hlc_timestamp < self.last_hlc_in_consensus:
            return

        # self.log.debug(f'ADDING {node_vk[:8]}\'s BLOCK INFO {block_info["hash"][:8]} TO NEEDS VALIDATION RESULTS STORE')
        # Store data about the tx so it can be processed for consensus later.
        if hlc_timestamp not in self.validation_results:
            self.validation_results[hlc_timestamp] = {}
            self.validation_results[hlc_timestamp]['solutions'] = {}
            self.validation_results[hlc_timestamp]['last_consensus_result'] = {}
            self.validation_results[hlc_timestamp]['last_check_info'] = {
                'ideal_consensus_possible': True,
                'eager_consensus_possible': True,
                'has_consensus': False,
                'solution': None
            }

        if self.validation_results[hlc_timestamp]['last_check_info']['has_consensus'] is True:
            # TODO why are we getting solutions from a bock in consensus??  Would we ever?
            # Is just returning an okay move?
            return

        if transaction_processed is not None and node_vk == self.wallet.verifying_key:
            '''
            self.log.debug(f'Adding transaction_processed for {hlc_timestamp}')
            self.log.debug(transaction_processed)
            '''
            self.validation_results[hlc_timestamp]['transaction_processed'] = transaction_processed

        '''
        if self.debug:
            self.log.debug(json.dumps({
                'type': 'tx_lifecycle',
                'file': 'validation_queue',
                'event': 'got_solution',
                'from': node_vk,
                'solution': block_info['hash'],
                'hlc_timestamp': hlc_timestamp,
                'system_time': time.time()
            }))
        '''

        # check if this node already gave us information
        if node_vk in self.validation_results[hlc_timestamp]['solutions']:
            # TODO this is a possible place to kick off re-checking consensus on Eager consensus blocks
            # Set the possible consensus flags back to True
            self.validation_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible'] = True
            self.validation_results[hlc_timestamp]['last_check_info']['eager_consensus_possible'] = True

        self.validation_results[hlc_timestamp]['solutions'][node_vk] = block_info

        super().append(hlc_timestamp)

    def awaiting_validation(self, hlc_timestamp):
        return hlc_timestamp in self.validation_results

    def check_num_of_solutions(self, hlc_timestamp):
        results = self.validation_results.get(hlc_timestamp)

        if results is None:
            return 0
        return len(self.validation_results[hlc_timestamp]['solutions'])

    def check_ideal_consensus_possible(self, hlc_timestamp):
        results = self.validation_results.get(hlc_timestamp)

        if results is None: return False
        last_check_info = results.get('last_check_info')
        if last_check_info is None: return False
        return last_check_info['ideal_consensus_possible']

    def check_eager_consensus_possible(self, hlc_timestamp):
        results = self.validation_results.get(hlc_timestamp)

        if results is None: return False
        last_check_info = results.get('last_check_info')
        if last_check_info is None: return False
        return last_check_info['eager_consensus_possible']

    def get_solution(self, hlc_timestamp, node_vk):
        results = self.validation_results.get(hlc_timestamp)
        if not results:
            return None
        return results['solutions'].get(node_vk)

    async def process_next(self):
        self.queue.sort()
        try:
            if self.hlc_has_solutions(self.queue[0]):
                self.process(hlc_timestamp=self.queue.pop(0))
        except IndexError:
            return
        except Exception as err:
            print(err)

    def process(self, hlc_timestamp):
        if not self.hlc_has_consensus(hlc_timestamp):
            try:
                self.validation_results[hlc_timestamp]['last_consensus_result'] = self.check_consensus(hlc_timestamp=hlc_timestamp)
            except Exception as err:
                print(err)

        consensus_result = self.validation_results[hlc_timestamp]['last_consensus_result']


        if self.debug:
            self.log.debug({'hlc_timestamp': hlc_timestamp, 'consensus_result': consensus_result})


        if self.testing:
            print({'consensus_result': consensus_result})

        if self.hlc_has_consensus(hlc_timestamp):
            try:
                winning_result = self.get_consensus_result(
                    solutions=self.validation_results[hlc_timestamp]['solutions'],
                    consensus_solution=consensus_result['solution']
                )
            except Exception as err:
                print(err)

            # Check that the previous block from the this solution matches the current block hash
            if self.is_next_block(winning_result['previous']):
                # self.log.info(f'{next_hlc_timestamp} HAS A CONSENSUS OF {consensus_info["solution"]}')
                if self.debug:
                    self.log.debug(json.dumps({
                        'type': 'tx_lifecycle',
                        'file': 'validation_queue',
                        'event': 'has_consensus',
                        'consensus_info': consensus_result,
                        'hlc_timestamp': hlc_timestamp,
                        'previous_block_hash': winning_result['previous'],
                        'system_time': time.time()
                    }))

                if consensus_result['matches_me']:
                    # if it matches us that means we did already processes this tx and the pending deltas should exist
                    # in the driver
                    try:
                        self.commit_consensus_block(hlc_timestamp=hlc_timestamp)
                    except Exception as err:
                        print(err)
                        self.log.debug(err)
                else:
                    try:
                        self.process_from_consensus_result(block_info=winning_result, hlc_timestamp=hlc_timestamp)
                        self.commit_consensus_block(hlc_timestamp=hlc_timestamp)
                    except Exception as err:
                        print(err)
                        self.log.debug(err)

                    # A couple different solutions exists here
                    if type(consensus_result.get('my_solution')) is str:
                        # There was consensus, I provided a solution and I wasn't in the consensus group. I need to rollback
                        # and check consensus again
                        self.log.debug(f'NOT IN CONSENSUS {hlc_timestamp} {consensus_result["my_solution"][:12]}')

                        # Stop validating any more block results
                        self.stop()
                        self.currently_processing = False

                        if self.debug or self.testing:
                            self.detected_rollback = True

                        asyncio.ensure_future(self.rollback())
            else:
                self.log.info("CHECKING FOR NEXT BLOCK")
                self.check_for_next_block()

    def check_for_next_block(self):
        for hlc_timestamp in self.validation_results:
            if self.validation_results[hlc_timestamp]['last_check_info']['has_consensus']:
                if self.is_next_block(self.validation_results[hlc_timestamp]['last_check_info'].get("solution")):
                    self.process(hlc_timestamp=hlc_timestamp)

    def check_consensus(self, hlc_timestamp):
        '''
            Consensus situations:
                ideal: one solution meets the consensus needed threshold and no more checking is required
                eager: no one solution meets the consensus threshold. Take the highest result if no other solution could overtake it.
                failure: Consensus is SPLIT, all results are in and the top results are tied. In this case take the numerical hex value that is the highest.
        '''
        # Get all the stored solutions for this hlc_timestamp
        try:
            solutions = self.validation_results[hlc_timestamp]['solutions']
        except KeyError as err:
            print(err)
            return

        # Get the number of current solutions
        total_solutions_received = len(solutions)

        # Get the number of current nodes and add yourself
        num_of_peers = len(self.get_peers_for_consensus()) + 1


        # TODO What should self.consensus_percent be set to?
        # determine the number of matching answers we need to form consensus
        consensus_needed = math.ceil(num_of_peers * (self.consensus_percent() / 100))

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
        '''
        self.log.debug({
            'total_solutions_received': total_solutions_received,
            'consensus_needed': consensus_needed,
            'num_of_peers': num_of_peers
        })
        '''
        if total_solutions_received < consensus_needed:
            # TODO Discuss possible scenario where enough peers go offline that we never reach the consensus number..
            return {
                'has_consensus': False
            }

        try:
            my_solution = solutions[self.wallet.verifying_key]['hash']
        except KeyError:
            my_solution = None

        solutions_missing = num_of_peers - total_solutions_received
        tally_info = self.tally_solutions(solutions=solutions)
        '''
        self.log.debug({
            'my_solution': my_solution,
            'solutions_missing': solutions_missing,
            'tally_info': tally_info
        })
        '''

        if self.validation_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible']:
            # Check ideal situation
            ideal_consensus_results = self.check_ideal_consensus(
                tally_info=tally_info,
                my_solution=my_solution,
                consensus_needed=consensus_needed,
                solutions_missing=solutions_missing
            )
            '''
            self.log.debug({
                'ideal_consensus_results': ideal_consensus_results
            })
            '''
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
                my_solution=my_solution,
                consensus_needed=consensus_needed
            )

    def check_ideal_consensus(self, tally_info, my_solution, solutions_missing, consensus_needed):
        top_solution = tally_info['results_list'][0]

        if top_solution['consensus_amount'] >= consensus_needed:
            return {
                'has_consensus': True,
                'ideal_consensus_possible': True,
                'consensus_type': 'ideal',
                'consensus_needed': consensus_needed,
                'solution': top_solution['solution'],
                'my_solution': my_solution,
                'matches_me': my_solution == top_solution['solution']
            }

        # consensus needed = 4
        # missing solutions = 1
        # Solution A has 3 matches
        # Solution B has 2 matches
        # If the missing one comes in and matches A, we're in ideal consensus
        # If the missing one comes in and matches B, we're in failed consensus
        # If the missing one never comes in we're stuck in no mans land.
        # TODO how to recover from this situation if the missing one never shows up (has happened a bunch in testing).

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
                'consensus_type': 'eager',
                'consensus_needed': consensus_needed,
                'solution': tally_info['results_list'][0]['solution'],
                'my_solution': my_solution,
                'matches_me': my_solution == tally_info['results_list'][0]['solution']
            }

        return {
            'has_consensus': False,
            'eager_consensus_possible': True
        }

    def check_failed_consensus(self, tally_info, my_solution, consensus_needed):
        for i in range(len(tally_info['top_solutions_list'])):
            tally_info['top_solutions_list'][i]['int'] = int(tally_info['top_solutions_list'][i]['solution'], 16)

        tally_info['top_solutions_list'] = sorted(tally_info['top_solutions_list'], key=lambda x: x['int'])

        return {
            'has_consensus': True,
            'consensus_type': 'failed',
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
        results_list = sorted(results_list, key=lambda x: x['consensus_amount'], reverse=True)

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

    def clear_my_solutions(self):
        for hlc_timestamp in self.validation_results:
            try:
                del self.validation_results[hlc_timestamp]['solutions'][self.wallet.verifying_key]

                # Set the possible consensus flags back to True
                self.validation_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible'] = True
                self.validation_results[hlc_timestamp]['last_check_info']['eager_consensus_possible'] = True
            except KeyError:
                pass

    def get_consensus_result(self, solutions, consensus_solution):
        for node_vk in solutions:
            if solutions[node_vk]['hash'] == consensus_solution:
                return solutions[node_vk]

    def commit_consensus_block(self, hlc_timestamp):
        # Hard apply these results on the driver
        self.hard_apply_block(hlc_timestamp=hlc_timestamp)

        # Set this as the last hlc that was in consensus
        self.last_hlc_in_consensus = hlc_timestamp

        # Remove all instances of this HLC from the checking queue to prevent re-checking it
        self.remove_all_hlcs_from_queue(hlc_timestamp=hlc_timestamp)

        # Clear all block results from memory because this block has consensus
        self.validation_results.pop(hlc_timestamp, None)

    def hlc_has_consensus(self, hlc_timestamp):
        validation_result = self.validation_results.get(hlc_timestamp)
        if validation_result is None:
            return False
        return validation_result['last_consensus_result'].get('has_consensus')

    def hlc_has_solutions(self, hlc_timestamp):
        validation_result = self.validation_results.get(hlc_timestamp)
        if validation_result is None:
            return False
        solutions = validation_result.get('solutions')
        if solutions is None:
            return False
        return len(solutions) > 0

    def count_solutions(self, hlc_timestamp):
        validation_result = self.validation_results.get(hlc_timestamp)
        if validation_result is None:
            return 0
        solutions = validation_result.get('solutions')
        if solutions is None:
            return 0
        return len(solutions)

    def remove_all_hlcs_from_queue(self, hlc_timestamp):
        self.queue = list(filter((hlc_timestamp).__ne__, self.queue))


    async def drop_bad_peers(self, all_block_results, consensus_result):
        correct_solution = consensus_result['solution']
        out_of_consensus = []
        for node_vk in all_block_results['solutions']:
            if all_block_results['solutions'][node_vk]['hash'] != correct_solution:
                out_of_consensus.append(node_vk)
        self.set_peers_not_in_consensus(out_of_consensus)

    def __setitem__(self, key, value):
        raise ReferenceError