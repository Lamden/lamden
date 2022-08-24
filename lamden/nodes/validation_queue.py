
from lamden.logger.base import get_logger
from lamden.nodes.queue_base import ProcessingQueue
from lamden.nodes.determine_consensus import DetermineConsensus
from lamden.nodes.multiprocess_consensus import MultiProcessConsensus
from lamden.storage import BlockStorage
from lamden.crypto.wallet import Wallet
import time

class ValidationQueue(ProcessingQueue):
    def __init__(self, driver, consensus_percent, wallet, hard_apply_block, stop_node, get_block_by_hlc,
                 get_block_from_network, blocks, testing=False, debug=False):
        super().__init__()

        self.log = get_logger("VALIDATION QUEUE")

        # The main dict for storing results from other nodes
        self.validation_results = dict()

        # Store confirmed solutions that I haven't got to yet
        self.last_hlc_in_consensus = ""
        self.max_hlc_in_consensus = ""

        self.get_block_by_hlc = get_block_by_hlc
        self.get_block_from_network = get_block_from_network
        self.hard_apply_block = hard_apply_block
        self.stop_node = stop_node

        self.determine_consensus = DetermineConsensus(
            consensus_percent=consensus_percent,
            my_wallet=wallet
        )

        self.multiprocess_consensus = MultiProcessConsensus(
            consensus_percent=consensus_percent,
            my_wallet=wallet,
            get_peers_for_consensus=self.get_peers_for_consensus
        )

        self.consensus_history = {}

        self.driver = driver
        self.wallet: Wallet = wallet
        self.blocks: BlockStorage = blocks

        # For debugging
        self.testing = testing
        self.debug = debug
        self.append_history = []
        self.validation_results_history = []
        self.detected_rollback = False
        self.last_reported = time.time()

        self.checking = False

    def append(self, processing_results):
        if not self.allow_append:
            return

        # self.log.debug(f'ADDING {block_info["hash"][:8]} TO NEEDS VALIDATION QUEUE')
        node_vk = processing_results["proof"].get('signer')

        # don't accept this solution if it's for an hlc_timestamp we already had consensus on
        hlc_timestamp = processing_results.get('hlc_timestamp')
        self.append_history.append(hlc_timestamp)

        if hlc_timestamp <= self.last_hlc_in_consensus:
            return

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
        if self.validation_results[hlc_timestamp]['solutions'].get(node_vk, None):
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

    async def process_next(self):
        if len(self.validation_results) > 0:
            next_hlc_timestamp = self[0]

            if next_hlc_timestamp <= self.last_hlc_in_consensus:
                self.flush_hlc(hlc_timestamp=next_hlc_timestamp)
                self.log.error(f"{next_hlc_timestamp} <= {self.last_hlc_in_consensus}")
                return

            self.check_one(next_hlc_timestamp)

            if self.hlc_has_consensus(next_hlc_timestamp):
                self.log.info(f'{next_hlc_timestamp} is in consensus, processing. Queue Length is {len(self.validation_results)} ')
                await self.commit_consensus_block(hlc_timestamp=next_hlc_timestamp)
                self.log.info(f'Done Processing, Queue Length now {len(self.validation_results)} ')

    async def process_all(self):
        # 1) Sort validation results object to get the earlist HLC
        # 2) Run consensus on that HLC
        # 3) Process the earliest if in consensus
        #self.log.debug('[START] process_next')
        if len(self.validation_results) > 0:
            next_hlc_timestamp = self[0]
            #self.log.debug(f'[Process Next] Checking: {next_hlc_timestamp}')

            # TODO This shouldn't be possible.
            if next_hlc_timestamp <= self.last_hlc_in_consensus:
                self.flush_hlc(hlc_timestamp=next_hlc_timestamp)
                self.log.error(f"{next_hlc_timestamp} <= {self.last_hlc_in_consensus}")
                return

            for hlc_timestamp in self.validation_results.keys():
                self.check_one(hlc_timestamp=hlc_timestamp)

            #await self.check_all()

            if self.hlc_has_consensus(next_hlc_timestamp):
                self.log.info(f'{next_hlc_timestamp} is in consensus, processing. Queue Length is {len(self.validation_results)} ')
                await self.commit_consensus_block(hlc_timestamp=next_hlc_timestamp)
                self.log.info(f'Done Processing, Queue Length now {len(self.validation_results)} ')
            else:
                if self.later_consensus_exists(hlc_timestamp=next_hlc_timestamp):
                    blocks = await self.get_block_from_network(hlc_timestamp=next_hlc_timestamp)
                    try:
                        block = self.get_consensus_block(blocks=blocks)
                    except Exception as err:
                        print(err)
                    if block:
                        await self.commit_consensus_block(block=block)

    def check_one(self, hlc_timestamp):
        #self.log.debug('[START] check_one')

        results = self.get_validation_result(hlc_timestamp=hlc_timestamp)

        if results is None:
            #self.log.debug('[STOP] check_one - results are None')
            return

        consensus_result = self.determine_consensus.check_consensus(
            solutions=results.get('solutions'),
            num_of_participants=len(self.get_peers_for_consensus()),
            last_check_info=results.get('last_check_info')
        )

        if consensus_result is not None:
            self.add_consensus_result(
                hlc_timestamp=hlc_timestamp,
                consensus_result=consensus_result
            )

        #self.log.debug('[STOP] check_one')

    async def check_all(self):
        if self.checking:
            return

        self.checking = True

        try:
            results_not_in_consensus = self.results_not_in_consensus
            if len(results_not_in_consensus) == 0:
                self.checking = False
                return

            all_consensus_results = await self.multiprocess_consensus.start(
                validation_results=results_not_in_consensus
            )

            for hlc_timestamp in all_consensus_results:
                if all_consensus_results.get(hlc_timestamp, None) is not None:
                    self.add_consensus_result(
                        hlc_timestamp=hlc_timestamp,
                        consensus_result=all_consensus_results[hlc_timestamp]
                    )

        except Exception as err:
            self.log.error(err)
            print(err)
        finally:
            self.checking = False

    async def process(self, hlc_timestamp):
        '''
        if self.debug:
            self.log.debug({'hlc_timestamp': hlc_timestamp, 'consensus_result': consensus_result})
        '''

        if self.hlc_has_consensus(hlc_timestamp):
            await self.commit_consensus_block(hlc_timestamp=hlc_timestamp)

    def add_consensus_result(self, hlc_timestamp: str, consensus_result: dict) -> None:
        #self.log.debug('[START] add_consensus_result')

        if consensus_result is None:
            #self.log.debug('[STOP] add_consensus_result - consensus_result is None')
            return

        has_consensus = consensus_result.get('has_consensus')
        if has_consensus is not None and has_consensus:
            self.validation_results[hlc_timestamp]['last_check_info'] = consensus_result
        else:
            ideal_consensus_possible = consensus_result.get('ideal_consensus_possible')
            if ideal_consensus_possible is not None:
                self.validation_results[hlc_timestamp]['last_check_info']['ideal_consensus_possible'] = ideal_consensus_possible

            eager_consensus_possible = consensus_result.get('eager_consensus_possible')
            if eager_consensus_possible is not None:
                self.validation_results[hlc_timestamp]['last_check_info']['eager_consensus_possible'] = eager_consensus_possible

        #self.log.debug('[STOP] add_consensus_result')

    def awaiting_validation(self, hlc_timestamp):
        return hlc_timestamp in self.validation_results

    @property
    def results_not_in_consensus(self):
        results = {}
        for hlc_timestamp in self.validation_results.keys():
            if not self.hlc_has_consensus(hlc_timestamp=hlc_timestamp):
                results[hlc_timestamp] = self.validation_results[hlc_timestamp]
        return results

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

    def later_consensus_exists(self, hlc_timestamp: str) -> bool:
        hlc_list = self.validation_results.keys()
        hlc_list = list(filter(lambda x: x != hlc_timestamp, hlc_list))
        hlc_list.sort()

        for hlc_timestamp in hlc_list:
            if self.hlc_has_consensus(hlc_timestamp):
                return True

        return False

    def get_consensus_block(self, blocks: list) -> dict:
        tally_results = {}
        for block in blocks:
            block_hash = block.get('hash')
            if tally_results.get(block_hash) is None:
                tally_results[block_hash] = 1
            else:
                tally_results[block_hash] += 1

        winning_hash = None
        ties = []
        for block_hash, tally in tally_results.items():
            winner_obj = {
                    'block_hash': block_hash,
                    'tally': tally
                }
            if winning_hash is None or tally > winning_hash.get('tally'):
                winning_hash = winner_obj
                ties = []
            else:
                if tally == winning_hash.get('tally'):
                    if len(ties) == 0:
                        ties.append(winning_hash)
                    ties.append(winner_obj)

        for block in blocks:
            if block.get('hash') == winning_hash.get('block_hash'):
                return block

    def get_result_hash_for_vk(self, hlc_timestamp, node_vk):
        results = self.validation_results.get(hlc_timestamp)
        if not results:
            return None
        return results['solutions'].get(node_vk)

    def is_earliest_hlc(self, hlc_timestamp):
        hlc_list = sorted(self.validation_results.keys())
        try:
            return hlc_timestamp == hlc_list[0]
        except:
            return False

    async def check_for_next_block(self):
        for hlc_timestamp in self.validation_results:
            try:
                if self.validation_results[hlc_timestamp]['last_check_info']['has_consensus']:
                    # self.log.debug(f"is {self.validation_results[hlc_timestamp]['last_check_info'].get('solution')} the next block? {self.is_next_block(self.validation_results[hlc_timestamp]['last_check_info'].get('solution'))}")
                    if self.is_earliest_hlc(hlc_timestamp):
                        # self.log.info(f"FOUND NEXT BLOCK, PROCESSING - {hlc_timestamp}")
                        await self.process(hlc_timestamp=hlc_timestamp)
                        return
            except:
                pass

    def clear_solutions(self, node_vk, max_hlc=None):
        for hlc in self.validation_results:
            if max_hlc is None or hlc > max_hlc:
                res = self.validation_results[hlc]['solutions'].pop(node_vk, None)
                if res is not None:
                    self.validation_results[hlc]['proofs'].pop(node_vk, None)
                    # Set the possible consensus flags back to True
                    self.validation_results[hlc]['last_check_info']['ideal_consensus_possible'] = True
                    self.validation_results[hlc]['last_check_info']['eager_consensus_possible'] = True

                    # TODO: should we clean results lookup here as well?

                    self.log.debug(f'Cleared results from node: {node_vk[:8]}, hlc: {hlc}')

    def get_last_consensus_result(self, hlc_timestamp):
        results = self.validation_results.get(hlc_timestamp, None)
        if results is None:
            return {}
        return results.get('last_check_info', {})

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

    def get_validation_result(self, hlc_timestamp):
        return self.validation_results.get(hlc_timestamp)

    def get_consensus_results(self, hlc_timestamp):
        validation_result = self.get_validation_result(hlc_timestamp=hlc_timestamp)
        if validation_result is None:
            return
        consensus_results = validation_result.get('last_check_info', {})
        consensus_solution = consensus_results.get('solution', '')
        return validation_result['result_lookup'].get(consensus_solution, {})

    def get_recreated_tx_message(self, hlc_timestamp):
        results = self.validation_results.get(hlc_timestamp)
        # TODO should we handle these exceptions here or throw them to caller?
        try:
            my_solution = results['solutions'].get(self.wallet.verifying_key)
            processing_results = results['result_lookup'].get(my_solution)

            return {
                'tx': processing_results['tx_result'].get('transaction'),
                'hlc_timestamp': hlc_timestamp,
                'signature': processing_results['tx_message'].get('signature'),
                'sender': processing_results['tx_message'].get('sender')
            }
        except:
            return None

    def consensus_matches_me(self, hlc_timestamp):
        validation_result = self.validation_results.get(hlc_timestamp, {})
        consensus_results = validation_result.get('last_check_info', {})
        consensus_solution = consensus_results.get('solution', '')

        solutions = validation_result.get('solutions', {})
        my_solution = solutions.get(self.wallet.verifying_key, None)

        return my_solution == consensus_solution

    async def commit_consensus_block(self, hlc_timestamp: str = None, block: dict = None):
        if hlc_timestamp is not None:
            # Get the tx results for this timestamp
            processing_results = self.get_consensus_results(hlc_timestamp=hlc_timestamp)

            # Hard apply these results on the driver
            new_block = await self.hard_apply_block(processing_results=processing_results)

        if block is not None:
            hlc_timestamp = block.get('hlc_timestamp')
            # Hard apply these results on the driver
            new_block = await self.hard_apply_block(block=block)

        # remove HLC from processing
        self.flush_hlc(hlc_timestamp=hlc_timestamp)

        if new_block is None:
            self.log.error(f"Error while minting block HLC: {hlc_timestamp}.")
            return

        self.set_last_hlc_in_consensus(hlc_timestamp=hlc_timestamp)
        hlcs = self.prune_earlier_results(consensus_hlc_timestamp=self.last_hlc_in_consensus)
        if len(hlcs) > 0:
            self.log.critical(f'Pruned {hlcs}')

    def flush_hlc(self, hlc_timestamp):
        # Clear all block results from memory because this block has consensus
        try:
            self.validation_results.pop(hlc_timestamp)
        except Exception as err:
            self.log.error(f'[flush_hlc] {err}')

    def hlc_has_consensus(self, hlc_timestamp):
        validation_result = self.validation_results.get(hlc_timestamp)
        if validation_result is None:
            return False
        return validation_result['last_check_info'].get('has_consensus')

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
        hlcs = []
        for hlc_timestamp in list(self.validation_results):
            if hlc_timestamp < consensus_hlc_timestamp:
                self.validation_results.pop(hlc_timestamp, None)
                hlcs.append(hlc_timestamp)

        return hlcs

    def clean_results_lookup(self, hlc_timestamp):
        validation_results = self.validation_results.get(hlc_timestamp)
        for solution in list(validation_results.get('result_lookup').keys()):
            exists = False
            for node in validation_results['solutions'].keys():
                if validation_results['solutions'][node] == solution:
                    exists = True
                    break
            if not exists:
                self.validation_results[hlc_timestamp]['result_lookup'].pop(solution)

    def set_last_hlc_in_consensus(self, hlc_timestamp: str) -> None:
        self.last_hlc_in_consensus = hlc_timestamp
        self.set_max_hlc_in_consensus(hlc_timestamp=hlc_timestamp)

    def set_max_hlc_in_consensus(self, hlc_timestamp: str) -> None:
        if hlc_timestamp > self.max_hlc_in_consensus:
            self.max_hlc_in_consensus = hlc_timestamp

    def get_node_list(self):
        return self.driver.driver.get(f'masternodes.S:members') or []

    def get_peers_for_consensus(self):
        all_peers = self.get_node_list()
        if self.wallet.verifying_key in all_peers:
            all_peers.remove(self.wallet.verifying_key)
        return all_peers

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
