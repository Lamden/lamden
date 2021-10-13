import asyncio
import math
import time
import json

from lamden.logger.base import get_logger
from lamden.nodes.queue_base import ProcessingQueue


class ValidationQueue(ProcessingQueue):
    def __init__(self, driver, consensus_percent, get_peers_for_consensus,
                 set_peers_not_in_consensus, wallet, hard_apply_block, stop_node, stop_all_queues,
                 start_all_queues, get_block_by_hlc, testing=False, debug=False):
        super().__init__()

        self.log = get_logger("VALIDATION QUEUE")

        # The main dict for storing results from other nodes
        self.validation_results = {}

        # Store confirmed solutions that I haven't got to yet
        self.last_hlc_in_consensus = ""

        self.get_block_by_hlc = get_block_by_hlc
        self.consensus_percent = consensus_percent
        self.get_peers_for_consensus = get_peers_for_consensus
        self.set_peers_not_in_consensus = set_peers_not_in_consensus
        self.hard_apply_block = hard_apply_block
        self.stop_node = stop_node
        self.stop_all_queues = stop_all_queues
        self.start_all_queues = start_all_queues

        self.driver = driver
        self.wallet = wallet

        # For debugging
        self.testing = testing
        self.debug = debug
        self.append_history = []
        self.validation_results_history = []
        self.detected_rollback = False

    def append(self, processing_results):
        # self.log.debug(f'ADDING {block_info["hash"][:8]} TO NEEDS VALIDATION QUEUE')
        node_vk = processing_results["proof"].get('signer')

        # don't accept this solution if it's for an hlc_timestamp we already had consensus on
        hlc_timestamp = processing_results.get('hlc_timestamp')
        self.append_history.append(hlc_timestamp)

        if hlc_timestamp <= self.last_hlc_in_consensus:
            block = self.get_block_by_hlc(hlc_timestamp=hlc_timestamp)
            return

        # TODO how late of an HLC timestamp are we going to accept?
        '''
        if hlc_timestamp < self.last_hlc_in_consensus:
            return
        '''

        # self.log.debug(f'ADDING {node_vk[:8]}\'s BLOCK INFO {block_info["hash"][:8]} TO NEEDS VALIDATION RESULTS STORE')
        # Store data about the tx so it can be processed for consensus later.
        if hlc_timestamp not in self.validation_results:
            self.validation_results[hlc_timestamp] = {}
            self.validation_results[hlc_timestamp]['solutions'] = {}
            self.validation_results[hlc_timestamp]['proofs'] = {}
            self.validation_results[hlc_timestamp]['result_lookup'] = {}
            self.validation_results[hlc_timestamp]['last_consensus_result'] = {}
            self.validation_results[hlc_timestamp]['last_check_info'] = {
                'ideal_consensus_possible': True,
                'eager_consensus_possible': True,
                'has_consensus': False,
                'solution': None
            }

            reconstructed_tx_message = processing_results['tx_message']
            reconstructed_tx_message['tx'] = processing_results['tx_result']['transaction']
            reconstructed_tx_message['hlc_timestamp'] = hlc_timestamp

            self.validation_results[hlc_timestamp]['transaction_processed'] = reconstructed_tx_message

        if self.validation_results[hlc_timestamp]['last_check_info']['has_consensus'] is True:
            # TODO why are we getting solutions from a bock in consensus??  Would we ever?
            # Is just returning an okay move?
            return

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

            self.clean_results_lookup(hlc_timestamp=hlc_timestamp)

        result_hash = processing_results["proof"].get('tx_result_hash')

        self.validation_results[hlc_timestamp]['solutions'][node_vk] = result_hash
        self.validation_results[hlc_timestamp]['proofs'][node_vk] = processing_results["proof"]

        if self.validation_results[hlc_timestamp]['result_lookup'].get(result_hash) is None:
            self.validation_results[hlc_timestamp]['result_lookup'][result_hash] = processing_results

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

    def get_result_hash_for_vk(self, hlc_timestamp, node_vk):
        results = self.validation_results.get(hlc_timestamp)
        if not results:
            return None
        return results['solutions'].get(node_vk)

    async def process_next(self):
        if len(self.validation_results) > 0:
            next_hlc_timestamp = self[0]

            if next_hlc_timestamp <= self.last_hlc_in_consensus:
                block = self.get_block_by_hlc(hlc_timestamp=next_hlc_timestamp)
                if block:
                    self.flush_hlc(next_hlc_timestamp)
                    return

            try:
                await self.process(hlc_timestamp=next_hlc_timestamp)
            except IndexError:
                return
            except Exception as err:
                print(err)

    async def process(self, hlc_timestamp):
        if not self.hlc_has_consensus(hlc_timestamp):
            try:
                self.validation_results[hlc_timestamp]['last_consensus_result'] = self.check_consensus(hlc_timestamp=hlc_timestamp)
            except Exception as err:
                print(err)

        consensus_result = self.get_last_consensus_result(hlc_timestamp=hlc_timestamp)
        '''
        if self.debug:
            self.log.debug({'hlc_timestamp': hlc_timestamp, 'consensus_result': consensus_result})
        '''
        if self.hlc_has_consensus(hlc_timestamp):
            try:
                winning_result = self.validation_results[hlc_timestamp]['result_lookup'].get(consensus_result['solution'], None)
            except Exception as err:
                print(err)

            if self.is_earliest_hlc(hlc_timestamp=hlc_timestamp):
                # self.log.info(f'{next_hlc_timestamp} HAS A CONSENSUS OF {consensus_info["solution"]}')
                '''
                if self.debug:
                    self.log.debug(json.dumps({
                        'type': 'tx_lifecycle',
                        'file': 'validation_queue',
                        'event': 'has_consensus',
                        'consensus_info': consensus_result,
                        'hlc_timestamp': hlc_timestamp,
                        'block_number': winning_result['hlc_timestamp'],
                        'system_time': time.time()
                    }))
                '''

                results = self.validation_results[hlc_timestamp]

                # if it matches us that means we did already processes this tx and the pending deltas should exist
                # in the driver
                try:
                    await self.commit_consensus_block(hlc_timestamp=hlc_timestamp)

                    if self.testing:
                        self.validation_results_history.append({hlc_timestamp: [{'matched_me':consensus_result['matches_me']}, results]})
                except Exception as err:
                    print(err)
                    self.log.debug(err)
            else:
                self.log.info("CHECKING FOR NEXT BLOCK")
                self.check_for_next_block()

    def is_earliest_hlc(self, hlc_timestamp):
        hlc_list = sorted(self.validation_results.keys())
        return hlc_timestamp == hlc_list[0]

    def check_for_next_block(self):
        for hlc_timestamp in self.validation_results:
            if self.validation_results[hlc_timestamp]['last_check_info']['has_consensus']:
                # self.log.debug(f"is {self.validation_results[hlc_timestamp]['last_check_info'].get('solution')} the next block? {self.is_next_block(self.validation_results[hlc_timestamp]['last_check_info'].get('solution'))}")
                if self.is_earliest_hlc(hlc_timestamp):
                    # self.log.info(f"FOUND NEXT BLOCK, PROCESSING - {hlc_timestamp}")
                    self.process(hlc_timestamp=hlc_timestamp)
                    return

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
            my_solution = solutions[self.wallet.verifying_key]
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
            solution = solutions[node]

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

    def get_processed_transaction(self, hlc_timestamp):
        results = self.validation_results.get(hlc_timestamp)
        return results.get('transaction_processed')

    def get_last_consensus_result(self, hlc_timestamp):
        results = self.validation_results.get(hlc_timestamp, None)
        if results is None:
            return {}
        return results.get('last_consensus_result', {})

    def get_proofs_from_results(self, hlc_timestamp):
        results = self.validation_results.get(hlc_timestamp)
        last_consensus_result = self.get_last_consensus_result(hlc_timestamp=hlc_timestamp)
        consensus_solution = last_consensus_result.get('solution')

        if not last_consensus_result.get('has_consensus'):
            return []

        all_proofs = results.get('proofs')

        proofs = []

        for node_vk in all_proofs:
            proof = all_proofs[node_vk]
            if proof.get('tx_result_hash') == consensus_solution:
                proofs.append(proof)

        return proofs

    def get_consensus_results(self, hlc_timestamp):
        validation_result = self.validation_results.get(hlc_timestamp, {})
        consensus_results = validation_result.get('last_consensus_result', {})
        consensus_solution = consensus_results.get('solution', '')
        return validation_result['result_lookup'].get(consensus_solution, {})

    def consensus_matches_me(self, hlc_timestamp):
        validation_result = self.validation_results.get(hlc_timestamp, {})
        consensus_results = validation_result.get('last_consensus_result', {})
        consensus_solution = consensus_results.get('solution', '')

        solutions = validation_result.get('solutions', {})
        my_solution = solutions.get(self.wallet.verifying_key, None)

        return my_solution == consensus_solution

    async def commit_consensus_block(self, hlc_timestamp):
        # Get the tx results for this timestamp
        processing_results = self.get_consensus_results(hlc_timestamp=hlc_timestamp)

        # Hard apply these results on the driver
        try:
            await self.hard_apply_block(processing_results=processing_results)
        except Exception as err:
            print(err)
            self.log.debug(err)

        # Set this as the last hlc that was in consensus
        if hlc_timestamp > self.last_hlc_in_consensus:
            self.last_hlc_in_consensus = hlc_timestamp

        # remove HLC from processing
        self.flush_hlc(hlc_timestamp=hlc_timestamp)

        # Remove any HLC results in validation results that might be earlier
        # TODO DO we want to do this?
        # self.prune_earlier_results(consensus_hlc_timestamp=hlc_timestamp)

    def flush_hlc(self, hlc_timestamp):
        # Clear all block results from memory because this block has consensus
        self.validation_results.pop(hlc_timestamp)

        # Remove all instances of this HLC from the checking queue to prevent re-checking it
        # self.remove_all_hlcs_from_queue(hlc_timestamp=hlc_timestamp)

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

    def prune_earlier_results(self, consensus_hlc_timestamp):
        for hlc_timestamp in self.validation_results:
            if hlc_timestamp < consensus_hlc_timestamp:
                self.validation_results.pop(hlc_timestamp, None)

    def clean_results_lookup(self, hlc_timestamp):
        validation_results = self.validation_results.get(hlc_timestamp)
        for solution in validation_results.get('result_lookup').keys():
            exists = False
            for node in validation_results['solutions'].keys():
                if validation_results['solutions'][node] == solution:
                    exists = True
                    break
            if not exists:
                self.validation_results['result_lookup'].pop(solution)

    async def drop_bad_peers(self, all_block_results, consensus_result):
        correct_solution = consensus_result['solution']
        out_of_consensus = []
        for node_vk in all_block_results['solutions']:
            if all_block_results['solutions'][node_vk] != correct_solution:
                out_of_consensus.append(node_vk)
        self.set_peers_not_in_consensus(out_of_consensus)

    def __setitem__(self, key, value):
        raise ReferenceError

    def __len__(self):
        return len(self.validation_results)

    def __getitem__(self, index):
        try:
            hlcs_to_process = [key for key in self.validation_results.keys()]
            hlcs_to_process.sort()
            return hlcs_to_process[index]
        except IndexError:
            return None