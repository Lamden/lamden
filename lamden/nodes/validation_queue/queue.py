import asyncio

from lamden.logger.base import get_logger
from lamden.nodes.queue_base import ProcessingFileQueue
from lamden.nodes.determine_consensus import DetermineConsensus
from lamden.nodes.multiprocess_consensus import MultiProcessConsensus
from lamden.network import Network
from lamden.config import STORAGE_HOME
from lamden.nodes.validation_queue.results import ValidationResults


class ValidationQueue(ProcessingFileQueue):
    def __init__(self, consensus_percent, state, network: Network, wallet, hard_apply_block, stop_node, testing=False,
                 debug=False, root=STORAGE_HOME.joinpath('validation_queue')):
        super().__init__(root=root)

        self.log = get_logger("VALIDATION QUEUE")

        self.state = state

        # The main dict for storing results from other nodes
        self.validation_results = ValidationResults()

        # Store confirmed solutions that I haven't got to yet
        self.state.metadata.last_hlc_in_consensus = ""

        self.hard_apply_block = hard_apply_block
        self.stop_node = stop_node

        self.network = network

        self.determine_consensus = DetermineConsensus(
            consensus_percent=consensus_percent,
            my_wallet=wallet
        )

        self.multiprocess_consensus = MultiProcessConsensus(
            consensus_percent=consensus_percent,
            my_wallet=wallet,
            get_peers_for_consensus=self.network.get_peers_for_consensus
        )

        self.wallet = wallet

        # For debugging
        self.testing = testing
        self.debug = debug
        self.append_history = []
        self.validation_results_history = []
        self.detected_rollback = False

        self.checking = False

    async def loop(self, wait=0):
        while self.running:
            if len(self.queue) > 0:
                for q in self.queue:
                    self.append(q)
            await asyncio.sleep(wait)

    def append(self, processing_results):
        # self.log.debug(f'ADDING {block_info["hash"][:8]} TO NEEDS VALIDATION QUEUE')
        node_vk = processing_results["proof"].get('signer')

        # don't accept this solution if it's for an hlc_timestamp we already had consensus on
        hlc_timestamp = processing_results.get('hlc_timestamp')
        self.append_history.append(hlc_timestamp)

        if hlc_timestamp <= self.state.metadata.last_hlc_in_consensus:
            block = self.state.blocks.get_block(v=hlc_timestamp)
            if block:
                return

        self.validation_results.add(hlc_timestamp=hlc_timestamp)

        if self.validation_results[hlc_timestamp]['last_check_info']['has_consensus'] is True:
            return

        # check if this node already gave us information
        self.validation_results.update_for_node(hlc_timestamp, node_vk)

        # Add solution
        self.validation_results.add_solution(processing_results, hlc_timestamp, node_vk)

    async def process_next(self):
        if len(self.validation_results) > 0:
            next_hlc_timestamp = self[0]

            if next_hlc_timestamp <= self.state.metadata.last_hlc_in_consensus:
                block = self.state.blocks.get_block(v=next_hlc_timestamp)
                if block:
                    self.validation_results.flush_hlc(next_hlc_timestamp)
                    await self.process_next()

            if self.validation_results.hlc_has_consensus(next_hlc_timestamp):
                await self.process(hlc_timestamp=next_hlc_timestamp)

    async def check_all(self):
        # TODO remove this try
        if self.checking:
            return

        self.checking = True

        try:
            results_not_in_consensus = self.validation_results.results_not_in_consensus
            if len(results_not_in_consensus) == 0:
                self.checking = False
                return

            all_consensus_results = await self.multiprocess_consensus.start(
                validation_results=results_not_in_consensus
            )

            for hlc_timestamp in all_consensus_results:
                if all_consensus_results.get(hlc_timestamp, None) is not None:
                    self.validation_results.add_consensus_result(
                        hlc_timestamp=hlc_timestamp,
                        consensus_result=all_consensus_results[hlc_timestamp]
                    )

        except Exception as err:
            self.log.error(err)
            print(err)

        self.checking = False

    async def process(self, hlc_timestamp):
        '''
        if self.debug:
            self.log.debug({'hlc_timestamp': hlc_timestamp, 'consensus_result': consensus_result})
        '''

        if self.validation_results.hlc_has_consensus(hlc_timestamp):
            results = self.validation_results.get(hlc_timestamp)
            consensus_result = self.validation_results.get_last_consensus_result(hlc_timestamp=hlc_timestamp)

            #if self.is_earliest_hlc(hlc_timestamp=hlc_timestamp):
            if True:
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

    def check_for_next_block(self):
        for hlc_timestamp in self.validation_results:
            if self.validation_results[hlc_timestamp]['last_check_info']['has_consensus']:
                # self.log.debug(f"is {self.validation_results[hlc_timestamp]['last_check_info'].get('solution')} the next block? {self.is_next_block(self.validation_results[hlc_timestamp]['last_check_info'].get('solution'))}")
                if self.validation_results.is_earliest_hlc(hlc_timestamp):
                    # self.log.info(f"FOUND NEXT BLOCK, PROCESSING - {hlc_timestamp}")
                    self.process(hlc_timestamp=hlc_timestamp)
                    return

    def clear_my_solutions(self):
        for hlc_timestamp in self.validation_results:
            try:
                del self.validation_results[hlc_timestamp]['solutions'][self.wallet.verifying_key]

                # Set the possible consensus flags back to True
                self.validation_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible'] = True
                self.validation_results[hlc_timestamp]['last_check_info']['eager_consensus_possible'] = True
            except KeyError:
                pass

    def get_recreated_tx_message(self, hlc_timestamp):
        results = self.validation_results.get(hlc_timestamp)
        my_solution = results['solutions'].get(self.wallet.verifying_key)
        processing_results = results['result_lookup'].get(my_solution)

        return {
            'tx': processing_results['tx_result'].get('transaction'),
            'hlc_timestamp': hlc_timestamp,
            'signature': processing_results['tx_message'].get('signature'),
            'sender': processing_results['tx_message'].get('signer')
        }

    async def commit_consensus_block(self, hlc_timestamp):
        # Get the tx results for this timestamp
        processing_results = self.validation_results.get_consensus_results(hlc_timestamp=hlc_timestamp)

        # Hard apply these results on the driver
        try:
            if hlc_timestamp <= self.state.metadata.last_hlc_in_consensus:
                print("stop")
            await self.hard_apply_block(processing_results=processing_results)
        except Exception as err:
            print(err)
            self.log.debug(err)

        # Set this as the last hlc that was in consensus
        if hlc_timestamp > self.state.metadata.last_hlc_in_consensus:
            self.state.metadata.last_hlc_in_consensus = hlc_timestamp

        # remove HLC from processing
        self.validation_results.flush_hlc(hlc_timestamp=hlc_timestamp)

        # Remove any HLC results in validation results that might be earlier
        # TODO DO we want to do this?
        # self.prune_earlier_results(consensus_hlc_timestamp=hlc_timestamp)

    def remove_all_hlcs_from_queue(self, hlc_timestamp):
        self.queue = list(filter((hlc_timestamp).__ne__, self.queue))

    def get_key_list(self):
        return [key for key in self.validation_results.keys()]

    def __setitem__(self, key, value):
        raise ReferenceError

    def __len__(self):
        return len(self.validation_results)

    def __getitem__(self, index):
        try:
            hlcs_to_process = self.get_key_list()
            hlcs_to_process.sort()
            return hlcs_to_process[index]
        except IndexError:
            return None


