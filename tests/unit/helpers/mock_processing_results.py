from lamden.crypto.wallet import Wallet
from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_tx_message, get_processing_results
from copy import deepcopy

class ValidationResults:
    def __init__(self, my_wallet=None):
        self.all_results = {}
        self.my_wallet = my_wallet

    def add_node_result(self, processing_results, wallet=None):
        hlc_timestamp = processing_results.get('hlc_timestamp')

        if self.all_results.get(hlc_timestamp) is None:
            self.all_results[hlc_timestamp] = {}
            self.all_results[hlc_timestamp]['solutions'] = {}
            self.all_results[hlc_timestamp]['proofs'] = {}
            self.all_results[hlc_timestamp]['result_lookup'] = {}
            self.all_results[hlc_timestamp]['last_consensus_result'] = {}
            self.all_results[hlc_timestamp]['last_check_info'] = {
                'ideal_consensus_possible': True,
                'eager_consensus_possible': True,
                'has_consensus': False,
                'solution': None
            }

        node_vk = processing_results["proof"].get('signer')

        if self.all_results[hlc_timestamp]['solutions'].get(node_vk, None):
            # TODO this is a possible place to kick off re-checking consensus on Eager consensus blocks
            # Set the possible consensus flags back to True
            self.all_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible'] = True
            self.all_results[hlc_timestamp]['last_check_info']['eager_consensus_possible'] = True

            self.clean_results_lookup(hlc_timestamp=hlc_timestamp)

        result_hash = processing_results["proof"].get('tx_result_hash')

        self.all_results[hlc_timestamp]['solutions'][node_vk] = result_hash
        self.all_results[hlc_timestamp]['proofs'][node_vk] = processing_results["proof"]

        if self.all_results[hlc_timestamp]['result_lookup'].get(result_hash) is None:
            self.all_results[hlc_timestamp]['result_lookup'][result_hash] = processing_results

    def add_test(self, num_of_nodes, includes_me=False):
        # create a tx message
        tx_message = get_tx_message()
        hlc_timestamp = tx_message['hlc_timestamp']

        # get specific processing results for a bunch of nodes
        # add all of those results to a ValidationResults obj

        for node_num in range(num_of_nodes):
            processing_results = get_processing_results(tx_message=tx_message)
            self.add_node_result(processing_results=processing_results)

        if (includes_me):
            # Add my solution
            my_processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.my_wallet)
            self.add_node_result(processing_results=my_processing_results)

        return hlc_timestamp

    def get_results(self):
        return self.all_results

    def get_result_hash(self, hlc_timestamp, node_vk):
        results = self.all_results.get(hlc_timestamp)
        return results['solutions'].get(node_vk, None)

    def get_solution_list(self, hlc_timestamp):
        results = self.all_results.get(hlc_timestamp)
        return list(results['result_lookup'])

    def add_solution(self, tx=None, tx_message=None, wallet=None, amount=None, to=None, receiver_wallet=None,
                     node_wallet=None, masternode=None, processing_results=None):

        masternode = masternode or Wallet()
        receiver_wallet = receiver_wallet or Wallet()
        node_wallet = node_wallet or Wallet()

        amount = amount or "10.5"
        to = to or receiver_wallet.verifying_key

        if tx_message is None:
            transaction = tx or get_new_currency_tx(wallet=wallet, amount=amount, to=to)

        tx_message = tx_message or get_tx_message(tx=transaction, node_wallet=masternode)

        processing_results = get_processing_results(tx_message=tx_message, node_wallet=node_wallet)

        self.add_node_result(
            processing_results=processing_results
        )

        return processing_results

    def add_solutions(self, amount_of_solutions, tx=None, tx_message=None, amount=None, wallet=None, to=None,
                      receiver_wallet=None, masternode=None, node_wallets=[]):

        if len(node_wallets) is 0:
            for w in range(amount_of_solutions):
                node_wallets.append(Wallet())

        if masternode is None:
            masternode = node_wallets[0]

        receiver_wallet = receiver_wallet or Wallet()

        wallet = wallet or Wallet()
        amount = amount or "10.5"
        to = to or receiver_wallet.verifying_key

        if tx_message is None:
            transaction = tx or get_new_currency_tx(wallet=wallet, amount=amount, to=to)

        tx_message = tx_message or get_tx_message(tx=transaction, node_wallet=masternode)

        processing_results = []

        for a in range(amount_of_solutions):
            if tx is None:
                processing_results.append(
                    self.add_solution(tx_message=tx_message, node_wallet=node_wallets[a])
                )

        return processing_results

    def alter_result(self, hlc_timestamp, node_vk, new_result):
        results = self.all_results.get(hlc_timestamp, None)
        if results is None:
            return

        old_result = self.all_results[hlc_timestamp]['solutions'][node_vk]
        self.all_results[hlc_timestamp]['solutions'][node_vk] = new_result
        old_lookup = self.all_results[hlc_timestamp]['result_lookup'].get(old_result, None)

        if old_lookup is not None:
            self.all_results[hlc_timestamp]['result_lookup'][new_result] = old_lookup
            del self.all_results[hlc_timestamp]['result_lookup'][old_result]


    def clean_results_lookup(self, hlc_timestamp):
        validation_results = self.all_results.get(hlc_timestamp)
        for solution in validation_results.get('result_lookup').keys():
            exists = False
            for node in validation_results['solutions'].keys():
                if validation_results['solutions'][node] == solution:
                    exists = True
                    break
            if not exists:
                self.all_results[hlc_timestamp]['result_lookup'].pop(solution)

    def add_bad_solution(self, node_wallet, tx_message, to=None):
        tx_message_bad = deepcopy(tx_message)

        if to is None:
            tx_message_bad['tx']['payload']['kwargs']['to'] = 'testing_vk'
        else:
            tx_message_bad['tx']['payload']['kwargs']['to'] = to

        return self.add_solution(
            tx_message=tx_message_bad,
            node_wallet=node_wallet
        )

    def add_solution_change_result(self, tx_message, hlc_timestamp, node_wallet, new_result):
        self.add_solution(
            tx_message=tx_message,
            node_wallet=node_wallet
        )
        self.alter_result(
            hlc_timestamp=hlc_timestamp,
            node_vk=node_wallet.verifying_key,
            new_result=new_result
        )

    def add_consensus_result(self, hlc_timestamp, consensus_result):
        if consensus_result.get('ideal_consensus_possible', None) is None:
            consensus_result['ideal_consensus_possible'] = self.all_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible']

        if consensus_result.get('eager_consensus_possible', None) is None:
            consensus_result['eager_consensus_possible'] = self.all_results[hlc_timestamp]['last_check_info']['eager_consensus_possible']

        self.all_results[hlc_timestamp]['last_check_info'] = consensus_result