class ValidationResults(dict):
    def add_consensus_result(self, hlc_timestamp, consensus_result):
        # If the result has neither ideal_consensus_possible or eager_consensus_possible then nothing was attempted
        if consensus_result.get('ideal_consensus_possible', None) is None and consensus_result.get('eager_consensus_possible', None) is None:
            return

        self[hlc_timestamp]['last_check_info'] = consensus_result

    def awaiting_validation(self, hlc_timestamp):
        return hlc_timestamp in self

    @property
    def results_not_in_consensus(self):
        results = {}
        for hlc_timestamp in self.keys():
            if not self.hlc_has_consensus(hlc_timestamp=hlc_timestamp):
                results[hlc_timestamp] = self[hlc_timestamp]
        return results

    def check_num_of_solutions(self, hlc_timestamp):
        results = self.get(hlc_timestamp)

        if results is None:
            return 0
        return len(self[hlc_timestamp]['solutions'])

    def check_ideal_consensus_possible(self, hlc_timestamp):
        try:
            return self[hlc_timestamp]['last_check_info']['ideal_consensus_possible']
        except KeyError:
            return False

    def check_eager_consensus_possible(self, hlc_timestamp):
        try:
            return self[hlc_timestamp]['last_check_info']['eager_consensus_possible']
        except KeyError:
            return False

    def get_result_hash_for_vk(self, hlc_timestamp, node_vk):
        results = self.get(hlc_timestamp)

        if results is None:
            return None

        return results['solutions'].get(node_vk)

    def is_earliest_hlc(self, hlc_timestamp):
        hlc_list = sorted(self.keys())

        if len(hlc_list) == 0:
            return False

        return hlc_timestamp == hlc_list[0]

    def get_last_consensus_result(self, hlc_timestamp):
        results = self.get(hlc_timestamp, None)

        if results is None:
            return {}

        return results.get('last_check_info', {})

    def get_proofs_from_results(self, hlc_timestamp):
        results = self.get(hlc_timestamp)
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
        validation_result = self.get(hlc_timestamp, {})
        consensus_results = validation_result.get('last_check_info', {})
        consensus_solution = consensus_results.get('solution', '')
        return validation_result['result_lookup'].get(consensus_solution, {})

    def flush_hlc(self, hlc_timestamp):
        # Clear all block results from memory because this block has consensus
        self.pop(hlc_timestamp)

        # Remove all instances of this HLC from the checking queue to prevent re-checking it
        # self.remove_all_hlcs_from_queue(hlc_timestamp=hlc_timestamp)

    def hlc_has_consensus(self, hlc_timestamp):
        validation_result = self.get(hlc_timestamp)
        if validation_result is None:
            return False
        return validation_result['last_check_info'].get('has_consensus')

    def prune_earlier_results(self, consensus_hlc_timestamp):
        for hlc_timestamp in self:
            if hlc_timestamp < consensus_hlc_timestamp:
                self.pop(hlc_timestamp, None)

    def clean_results_lookup(self, hlc_timestamp):
        validation_results = self.get(hlc_timestamp)
        for solution in validation_results.get('result_lookup').keys():
            exists = False
            for node in validation_results['solutions'].keys():
                if validation_results['solutions'][node] == solution:
                    exists = True
                    break
            if not exists:
                self['result_lookup'].pop(solution)

    def add(self, hlc_timestamp):
        if hlc_timestamp not in self:
            self[hlc_timestamp] = {}
            self[hlc_timestamp]['solutions'] = {}
            self[hlc_timestamp]['proofs'] = {}
            self[hlc_timestamp]['result_lookup'] = {}
            self[hlc_timestamp]['last_consensus_result'] = {}
            self[hlc_timestamp]['last_check_info'] = {
                'ideal_consensus_possible': True,
                'eager_consensus_possible': True,
                'has_consensus': False,
                'solution': None
            }

    def update_for_node(self, hlc_timestamp, node_vk):
        if self[hlc_timestamp]['solutions'].get(node_vk, None):
            # TODO this is a possible place to kick off re-checking consensus on Eager consensus blocks
            # Set the possible consensus flags back to True
            self[hlc_timestamp]['last_check_info']['ideal_consensus_possible'] = True
            self[hlc_timestamp]['last_check_info']['eager_consensus_possible'] = True

            self.clean_results_lookup(hlc_timestamp=hlc_timestamp)

    def add_solution(self, processing_results, hlc_timestamp, node_vk):
        result_hash = processing_results["proof"].get('tx_result_hash')
        self[hlc_timestamp]['solutions'][node_vk] = result_hash
        self[hlc_timestamp]['proofs'][node_vk] = processing_results["proof"]

        if self[hlc_timestamp]['result_lookup'].get(result_hash) is None:
            self[hlc_timestamp]['result_lookup'][result_hash] = processing_results

    def consensus_matches_vk(self, hlc_timestamp, verifying_key):
        validation_result = self.get(hlc_timestamp, {})
        consensus_results = validation_result.get('last_check_info', {})
        consensus_solution = consensus_results.get('solution', '')

        solutions = validation_result.get('solutions', {})
        my_solution = solutions.get(verifying_key, None)

        return my_solution == consensus_solution


class ConsensusInfo:
    def __init__(self):
        self.ideal_consensus_possible = True
        self.eager_consensus_possible = True
        self.has_consensus = False
        self.solution = None


class Result:
    def __init__(self):
        self.solutions = {}
        self.proofs = {}
        self.result_lookup = {}
        self.last_consensus_result = {}
        self.last_check_info = ConsensusInfo()