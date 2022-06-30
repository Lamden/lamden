import math
from lamden.logger.base import get_logger

class DetermineConsensus:
    def __init__(self, consensus_percent, my_wallet):

        self.consensus_percent = consensus_percent
        self.vk = my_wallet.verifying_key
        self.log  = get_logger("Determine Consensus")

    def check_consensus(self, solutions, num_of_participants, last_check_info):
        '''
            Consensus situations:
                ideal: one solution meets the consensus needed threshold and no more checking is required
                eager: no one solution meets the consensus threshold. Take the highest result if no other solution could overtake it.
                failure: Consensus is SPLIT, all results are in and the top results are tied. In this case take the numerical hex value that is the highest.
        '''

        #self.log.debug('[START] check_consensus')

        # Get the number of current solutions
        total_solutions_received = len(solutions)

        # TODO What should self.consensus_percent be set to?
        # determine the number of matching answers we need to form consensus
        # print({'num_of_participants': num_of_participants})
        # print({'consensus_amount': self.consensus_percent()})
        # print({'consensus_percent': self.consensus_percent() / 100})

        consensus_needed = math.ceil(num_of_participants * (self.consensus_percent() / 100))
        # print({'consensus_needed': consensus_needed, 'consensus_percent': self.consensus_percent() })

        '''
        Return if we don't have enough responses to attempt an ideal consensus check
        Which means consensus on any block solution doesn't start till we have at least enough respondents to get a
            first attempt at ideal consensus
        This COULD mean that block production stalls for a moment if a lot of node go offline.. but I'm not 100% sure
            if that is a real possibility.

        Example:
            num_of_participants = 10 (there are 10 peers currently marked by the network as connected and in_conensus
            consensus_needed = 6 (51% rounded up)
            total_solutions_received = 6 (we can now start checking consensus moving from ideal to eager to
                                          failure as more solutions arrive)
        '''
        '''
        self.log.debug({
            'total_solutions_received': total_solutions_received,
            'consensus_needed': consensus_needed,
            'num_of_participants': num_of_participants
        })
        '''
        if total_solutions_received < consensus_needed:
            #self.log.debug('[STOP] check_consensus - 1')

            # TODO Discuss possible scenario where enough peers go offline that we never reach the consensus number..
            return {
                'has_consensus': False
            }

        my_solution = solutions.get(self.vk, None)

        solutions_missing = num_of_participants - total_solutions_received
        tally_info = self.tally_solutions(solutions=solutions)
        # print({'tally_info':tally_info})


        self.log.debug({
            'num_of_participants': num_of_participants,
            'my_solution': my_solution,
            'solutions_missing': solutions_missing,
            'tally_info': tally_info,
            'consensus_needed': consensus_needed
        })

        if last_check_info.get('ideal_consensus_possible', False):
            # Check ideal situation
            ideal_consensus_results = self.check_ideal_consensus(
                tally_info=tally_info,
                my_solution=my_solution,
                consensus_needed=consensus_needed,
                solutions_missing=solutions_missing
            )
            # print({'ideal_consensus_results':ideal_consensus_results})

            self.log.debug({
                'ideal_consensus_results': ideal_consensus_results
            })

            # Return if we found ideal consensus on a solution
            # or there are still enough respondents left that ideal consensus is possible
            if ideal_consensus_results['has_consensus'] or ideal_consensus_results['ideal_consensus_possible']:
                #self.log.debug('[STOP] check_consensus - 2')
                return ideal_consensus_results

        if last_check_info.get('eager_consensus_possible', False):
            # Check eager situation
            eager_consensus_results = self.check_eager_consensus(
                tally_info=tally_info,
                my_solution=my_solution,
                consensus_needed=consensus_needed,
                solutions_missing=solutions_missing
            )
            self.log.debug({
                'eager_consensus_results': eager_consensus_results
            })

            # Return if we found eager consensus on a solution
            # or there are still enough respondents left that eager consensus is possible
            if eager_consensus_results['has_consensus'] or eager_consensus_results['eager_consensus_possible']:
                #self.log.debug('[STOP] check_consensus - 3')
                return eager_consensus_results

            # Return Failed situation if ideal and eager consensus is not possible
            # This should always return a consensus result
            failed_consensus_results = self.check_failed_consensus(
                tally_info=tally_info,
                my_solution=my_solution,
                consensus_needed=consensus_needed
            )

            self.log.debug({
                'failed_consensus_results': failed_consensus_results
            })
            #self.log.debug('[STOP] check_consensus - 4')
            return failed_consensus_results

        #self.log.debug('[STOP] check_consensus - 5')


    def check_ideal_consensus(self, tally_info, my_solution, solutions_missing, consensus_needed):
        #self.log.debug('[START] check_ideal_consensus')
        top_solution = tally_info['results_list'][0]

        if top_solution['consensus_amount'] >= consensus_needed:
            #self.log.debug('[STOP] check_ideal_consensus - 1')
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
            #self.log.debug('[STOP] check_ideal_consensus - 2')
            return {
                'has_consensus': False,
                'ideal_consensus_possible': True
            }

        #self.log.debug('[STOP] check_ideal_consensus - 3')
        return {
            'has_consensus': False,
            'ideal_consensus_possible': False
        }

    def check_eager_consensus(self, tally_info, my_solution, solutions_missing, consensus_needed):
        #self.log.debug('[START] check_eager_consensus')
        # if consensus is tied and there are not more expected solutions then eager consensus is not possible
        if tally_info['is_tied'] and solutions_missing == 0:
            #self.log.debug('[STOP] check_eager_consensus - 1')
            return {
                'has_consensus': False,
                'eager_consensus_possible': False
            }

        # if the winning solution is more than the next best + any new possible solutions then we have eager consensus
        if tally_info['results_list'][0]['consensus_amount'] > tally_info['results_list'][1][
            'consensus_amount'] + solutions_missing:
            #self.log.debug('[STOP] check_eager_consensus - 2')
            return {
                'has_consensus': True,
                'eager_consensus_possible': True,
                'consensus_type': 'eager',
                'consensus_needed': consensus_needed,
                'solution': tally_info['results_list'][0]['solution'],
                'my_solution': my_solution,
                'matches_me': my_solution == tally_info['results_list'][0]['solution']
            }

        #self.log.debug('[STOP] check_eager_consensus - 3')

        return {
            'has_consensus': False,
            'eager_consensus_possible': True
        }

    def check_failed_consensus(self, tally_info, my_solution, consensus_needed):
        #self.log.debug('[START] check_failed_consensus')
        for i in range(len(tally_info['top_solutions_list'])):
            tally_info['top_solutions_list'][i]['int'] = int(tally_info['top_solutions_list'][i]['solution'], 16)

        tally_info['top_solutions_list'] = sorted(tally_info['top_solutions_list'], key=lambda x: x['int'])

        #self.log.debug('[STOP] check_failed_consensus')
        return {
            'has_consensus': True,
            'consensus_type': 'failed',
            'consensus_needed': consensus_needed,
            'solution': tally_info['top_solutions_list'][0]['solution'],
            'my_solution': my_solution,
            'matches_me': my_solution == tally_info['top_solutions_list'][0]['solution'],
            'ideal_consensus_possible': False,
            'eager_consensus_possible': False
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