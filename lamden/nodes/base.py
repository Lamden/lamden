import asyncio
import gc
import hashlib
import json
import time
import uvloop

from copy import deepcopy
from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver
from contracting.db.encoder import convert_dict, encode
from contracting.execution.executor import Executor
from lamden import storage, router, rewards, upgrade, contracts
from lamden.contracts import sync
from lamden.crypto.wallet import Wallet
from lamden.logger.base import get_logger
from lamden.network import Network
from lamden.nodes import system_usage
from lamden.nodes import processing_queue, validation_queue
from lamden.nodes.processors import work, block_contender
from lamden.nodes.filequeue import FileQueue
from lamden.nodes.hlc import HLC_Clock
from lamden.crypto.canonical import tx_hash_from_tx, block_from_tx_results, recalc_block_info, tx_result_hash_from_tx_result_object
from lamden.nodes.events import Event, EventWriter

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

BLOCK_SERVICE = 'catchup'
GET_LATEST_BLOCK = 'get_latest_block'
GET_BLOCK = "get_block"
GET_CONSTITUTION = "get_constitution"
GET_ALL_PEERS = "get_all_peers"
NEW_BLOCK_SERVICE = 'new_blocks'
NEW_BLOCK_EVENT = 'new_block'
NEW_BLOCK_REORG_EVENT = 'block_reorg'
WORK_SERVICE = 'work'
CONTENDER_SERVICE = 'contenders'

class NewBlock(router.Processor):
    def __init__(self, driver: ContractDriver):
        self.q = []
        self.driver = driver
        self.log = get_logger('NBN')

    async def process_message(self, msg):
        self.q.append(msg)

    async def wait_for_next_nbn(self):
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        nbn = self.q.pop(0)

        self.q.clear()

        return nbn

    def clean(self, height):
        self.q = [nbn for nbn in self.q if nbn['number'] > height]


def ensure_in_constitution(verifying_key: str, constitution: dict):
    masternodes = constitution['masternodes']
    delegates = constitution['delegates']

    is_masternode = verifying_key in masternodes.values()
    is_delegate = verifying_key in delegates.values()

    assert is_masternode or is_delegate, 'You are not in the constitution!'

class Node:
    def __init__(self, socket_base,  wallet, constitution: dict, bootnodes={}, blocks=storage.BlockStorage(),
                 driver=ContractDriver(), delay=None, debug=True, testing=False, seed=None, bypass_catchup=False, node_type=None,
                 genesis_path=contracts.__path__[0], reward_manager=rewards.RewardManager(), consensus_percent=None,
                 nonces=storage.NonceStorage(), parallelism=4, should_seed=True, metering=False, tx_queue=FileQueue(),
                 socket_ports=None):

        self.consensus_percent = consensus_percent or 51
        self.processing_delay_secs = delay or {
            'base': 0.75,
            'self': 0.75
        }
        # amount of consecutive out of consensus solutions we will tolerate from out of consensus nodes
        self.tx_queue = tx_queue

        self.driver = driver
        self.nonces = nonces
        self.event_writer = EventWriter()

        self.seed = seed

        self.blocks = blocks
        self.current_block_height = 0

        self.log = get_logger('Base')
        self.debug = debug
        self.testing = testing

        self.debug_stack = []
        self.debug_processed_hlcs = []
        self.debug_processing_results = []
        self.debug_reprocessing_results = {}
        self.debug_blocks_processed = []
        self.debug_timeline = []
        self.debug_sent_solutions = []
        self.debug_last_checked_main = time.time()
        self.debug_last_checked_val = time.time()
        self.debug_loop_counter = {
            'main': 0,
            'validation': 0,
            'file_check': 0
        }

        self.log.propagate = debug
        self.socket_base = socket_base
        self.wallet = wallet
        self.hlc_clock = HLC_Clock()
        self.last_processed_hlc = self.hlc_clock.get_new_hlc_timestamp()

        self.system_monitor = system_usage.SystemUsage()

        self.genesis_path = genesis_path

        self.client = ContractingClient(
            driver=self.driver,
            submission_filename=genesis_path + '/submission.s.py'
        )

        self.bootnodes = bootnodes
        self.constitution = constitution
        self.should_seed = should_seed

        if self.should_seed:
            self.seed_genesis_contracts()

        self.upgrade_manager = upgrade.UpgradeManager(client=self.client, wallet=self.wallet, node_type=node_type)

        self.network = Network(
            debug=self.debug,
            testing=self.testing,
            wallet=wallet,
            socket_base=socket_base,
            socket_ports=socket_ports
        )

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver, metering=metering)
        self.reward_manager = reward_manager

        self.new_block_processor = NewBlock(driver=self.driver)

        self.main_processing_queue = processing_queue.TxProcessingQueue(
            testing=self.testing,
            debug=self.debug,
            driver=self.driver,
            client=self.client,
            wallet=self.wallet,
            hlc_clock=self.hlc_clock,
            processing_delay=lambda: self.processing_delay_secs,
            executor=self.executor,
            get_last_processed_hlc=self.get_last_processed_hlc,                         # Abstract
            get_last_hlc_in_consensus=self.get_last_hlc_in_consensus,                   # Abstract
            stop_node=self.stop,
            reward_manager=self.reward_manager,
            reprocess=self.reprocess,
            check_if_already_has_consensus=self.check_if_already_has_consensus,         # Abstract
            pause_all_queues=self.pause_all_queues,
            unpause_all_queues=self.unpause_all_queues
        )

        self.validation_queue = validation_queue.ValidationQueue(
            testing=self.testing,
            driver=self.driver,
            debug=self.debug,
            consensus_percent=lambda: self.consensus_percent,
            get_block_by_hlc=self.get_block_by_hlc,                                     # Abstract
            hard_apply_block=self.hard_apply_block,                                     # Abstract
            wallet=self.wallet,
            stop_node=self.stop,
            network=self.network
        )

        self.total_processed = 0
        # how long to hold items in queue before processing

        self.work_validator = work.WorkValidator(
            wallet=wallet,
            main_processing_queue=self.main_processing_queue,
            hlc_clock=self.hlc_clock,
            get_last_processed_hlc=self.get_last_processed_hlc,
            stop_node=self.stop,
            network=self.network
        )

        self.block_contender = block_contender.Block_Contender(
            testing=self.testing,
            debug=self.debug,
            validation_queue=self.validation_queue,
            get_block_by_hlc=self.get_block_by_hlc,
            wallet=self.wallet,
            network=self.network
        )

        self.network.add_service(WORK_SERVICE, self.work_validator)
        self.network.add_service(CONTENDER_SERVICE, self.block_contender)

        self.network.add_action(GET_LATEST_BLOCK, self.get_latest_block)
        self.network.add_action(GET_BLOCK, self.blocks.get_block)
        self.network.add_action(GET_CONSTITUTION, self.make_constitution)


        self.running = False
        self.upgrade = False

        self.bypass_catchup = bypass_catchup

    def __del__(self):
        self.network.stop()
        self.system_monitor.stop()

    @property
    def node_type(self):
        return self.upgrade_manager.node_type

    async def start(self):
        # Start running
        self.running = True

        if self.debug:
            asyncio.ensure_future(self.system_monitor.start(delay_sec=120))

        await self.network.start()

        await asyncio.sleep(2)

        if self.should_seed:
            await self.start_new_network()
        else:
            await self.join_existing_network()
            await self.catchup()

        self.driver.clear_pending_state()

        self.start_all_queues()
        asyncio.ensure_future(self.check_main_processing_queue())
        asyncio.ensure_future(self.check_validation_queue())

    async def start_new_network(self):
        for vk, ip in self.bootnodes.items():
            print({"vk": vk, "ip": ip})
            self.log.info({"vk": vk, "ip": ip})

            if vk != self.wallet.verifying_key:
                # Use it to boot up the network
                self.network.connect(
                    ip=ip,
                    vk=vk
                )

        # await self.network.connected_to_all_peers()

    async def join_existing_network(self):
        bootnode = None

        # Connect to a node on the network
        for vk, ip in self.bootnodes.items():
            print({"vk": vk, "ip": ip})
            self.log.info({"vk": vk, "ip": ip})

            if vk != self.wallet.verifying_key:
                # Use it to boot up the network
                self.network.connect(
                    ip=ip,
                    vk=vk
                )
                await asyncio.sleep(5)

                # We only need one bootnode, so if we connected then we're good
                if self.network.peers[vk].running:
                    bootnode = self.network.peers[vk]
                    break

        if bootnode is None:
            print("Could not connect to any bootnodes!")
            print(self.bootnodes)
            self.log.error("Could not connect to any bootnodes!")
            self.log.error(self.bootnodes)

            return False

        # Get the rest of the nodes from our bootnode
        response = bootnode.get_node_list()
        node_list = response.get('node_list')

        # Create a constitution file
        self.constitution = {
            'masternodes': [],
            'delegates':  []
        }

        # Populate constitution with node info
        for node_info in node_list:
            node_type = node_info.get('node_type')
            vk = node_info.get('vk')
            if node_type and vk:
                self.constitution[f'{node_type}s'].append(vk)

        self.constitution[f'{self.node_type}s'].append(self.wallet.verifying_key)

        # Create genesis contracts
        self.seed_genesis_contracts()

        # Connect to all nodes in the network
        for node_info in node_list:
            vk = node_info.get('vk')
            ip = node_info.get('ip')

            print({"vk": vk, "ip": ip})
            self.log.info({"vk": vk, "ip": ip})

            if vk != self.wallet.verifying_key:
                # connect to peer
                self.network.connect(
                    ip=ip,
                    vk=vk
                )

        # await self.network.connected_to_all_peers()

        return True


    async def stop(self):
        # Kill the router and throw the running flag to stop the loop
        self.log.error("!!!!!! STOPPING NODE !!!!!!")
        self.network.stop()
        self.system_monitor.stop()
        self.running = False

        await self.stop_all_queues()

        self.log.error("!!!!!! STOPPED NODE !!!!!!")

    async def catchup(self, peer_vk=None):
        # Get the current latest block stored and the latest block of the network
        self.log.info('Running catchup.')

        # Get the Node's current height
        current = self.get_current_height()

        catchup_peer = None

        if peer_vk:
            catchup_peer = self.network.peers[peer_vk]
        else:
            # get the peer at the highest block height
            for _, peer in self.network.peers.items():
                if not peer.running:
                    continue

                if not catchup_peer:
                    catchup_peer = peer

                if peer.latest_block > catchup_peer.latest_block:
                    catchup_peer = peer

        if not catchup_peer:
            self.log.error(f'No peers available for catchup!')
            return

        self.log.info(f'Contacting Peer {catchup_peer.ip} for catchup.')
        self.log.info({'current': current})

        await self.run_catchup(peer=catchup_peer)

    async def run_catchup(self, peer):
        current = self.get_current_height()

        while current < peer.latest_block:
            next_block_num = current + 1
            response = peer.get_block(block_num=next_block_num)
            self.log.info(response)

            if type(response) is dict:
                new_block = response.get("block_info")
                self.log.info(new_block)

                if new_block:
                    if new_block.get('number') == next_block_num:
                        # Apply state to DB
                        self.apply_state_changes_from_block(block=new_block)

                        # Store the block in the block db
                        encoded_block = encode(new_block)
                        encoded_block = json.loads(encoded_block)

                        self.blocks.store_block(block=encoded_block)

                        # Set the current block hash and height
                        self.update_block_db(block=encoded_block)

                        # create New Block Event
                        self.event_writer.write_event(Event(
                            topics=[NEW_BLOCK_EVENT],
                            data=encoded_block
                        ))
                    else:
                        self.log.error("Incorrect Block Number response in catchup!")
                        print("Incorrect Block Number response in catchup!")
            else:
                self.log.error(f"Cannot find block {next_block_num} on node {peer.vk}.  Trying again...")
                print(f"Cannot find block {next_block_num} on node {peer.vk}.  Trying again...")

                await asyncio.sleep(5)

            current = next_block_num


    def start_all_queues(self):
        self.log.info("!!!!!! STARTING ALL QUEUES !!!!!!")
        self.main_processing_queue.start()
        self.validation_queue.start()
        self.log.info(f"main_processing_queue running: {self.main_processing_queue.running}")
        self.log.info(f"validation_queue running: {self.validation_queue.running}")

    async def stop_all_queues(self):
        self.log.info("!!!!!! STOPPING ALL QUEUES !!!!!!")
        self.main_processing_queue.stop()
        self.validation_queue.stop()

        await self.main_processing_queue.stopping()
        self.log.info("!!!!!! main_processing_queue STOPPED !!!!!!")
        await self.validation_queue.stopping()
        self.log.info("!!!!!! validation_queue STOPPED !!!!!!")

        self.log.info(f"main_processing_queue running: {self.main_processing_queue.running}")
        self.log.info(f"validation_queue running: {self.validation_queue.running}")

    def unpause_all_queues(self):
        self.log.info("!!!!!! UNPAUSING ALL QUEUES !!!!!!")
        self.main_processing_queue.unpause()
        self.validation_queue.unpause()
        self.log.info(f"main_processing_queue paused: {self.main_processing_queue.paused}")
        self.log.info(f"validation_queue paused: {self.validation_queue.paused}")

    async def pause_all_queues(self):
        self.log.info("!!!!!! PAUSING ALL QUEUES !!!!!!")
        self.main_processing_queue.pause()
        self.validation_queue.pause()

        await self.main_processing_queue.pausing()
        self.log.info("!!!!!! main_processing_queue PAUSED !!!!!!")
        await self.validation_queue.pausing()
        self.log.info("!!!!!! validation_queue PAUSED !!!!!!")

        self.log.info(f"main_processing_queue paused: {self.main_processing_queue.paused}")
        self.log.info(f"validation_queue paused: {self.validation_queue.paused}")

    async def stop_main_processing_queue(self, force=False):
        self.main_processing_queue.stop()
        if force:
            self.main_processing_queue.currently_processing = False
        await self.main_processing_queue.stopping()

    def start_main_processing_queue(self):
        self.main_processing_queue.start()

    async def check_tx_queue(self):
        while self.running:
            if len(self.tx_queue) > 0:
                tx_from_file = self.tx_queue.pop(0)
                # TODO sometimes the tx info taken off the filequeue is None, investigate
                if tx_from_file is not None:
                    tx_message = self.make_tx_message(tx=tx_from_file)

                    # send the tx to the rest of the network
                    asyncio.ensure_future(self.network.publisher.publish(topic=WORK_SERVICE, msg=tx_message))

                    # add this tx the processing queue so we can process it
                    self.main_processing_queue.append(tx=tx_message)

            self.debug_loop_counter['file_check'] = self.debug_loop_counter['file_check'] + 1
            await asyncio.sleep(0)

    async def check_main_processing_queue(self):
        while self.running:
            if len(self.main_processing_queue) > 0 and self.main_processing_queue.active:
                self.main_processing_queue.start_processing()
                await self.process_main_queue()
                self.main_processing_queue.stop_processing()

            self.debug_loop_counter['main'] = self.debug_loop_counter['main'] + 1
            await asyncio.sleep(0)

    async def check_validation_queue(self):
        while self.running:
            if len(self.validation_queue.validation_results) > 0 and self.validation_queue.active:
                self.validation_queue.start_processing()
                await self.validation_queue.check_all()
                await self.validation_queue.process_next()
                self.validation_queue.stop_processing()

            self.debug_loop_counter['validation'] = self.debug_loop_counter['validation'] + 1
            await asyncio.sleep(0)

    async def process_main_queue(self):
        try:
            processing_results = await self.main_processing_queue.process_next()

            if processing_results:
                hlc_timestamp = processing_results.get('hlc_timestamp')

                if self.testing:
                    self.debug_processing_results.append(processing_results)

                if hlc_timestamp <= self.get_last_hlc_in_consensus():
                    return

                self.last_processed_hlc = hlc_timestamp

                try:
                    self.soft_apply_current_state(hlc_timestamp=hlc_timestamp)
                except Exception as err:
                    print(err)

                self.store_solution_and_send_to_network(processing_results=processing_results)
        except Exception as err:
            self.log.error(err)

    def store_solution_and_send_to_network(self, processing_results):

        self.send_solution_to_network(processing_results=processing_results)

        processing_results['proof']['tx_result_hash'] = tx_result_hash_from_tx_result_object(
            tx_result=processing_results['tx_result'],
            hlc_timestamp=processing_results['hlc_timestamp']
        )

        self.validation_queue.append(
            processing_results=processing_results
        )

    def send_solution_to_network(self, processing_results):
        asyncio.ensure_future(self.network.publisher.publish(topic=CONTENDER_SERVICE, msg=processing_results))

    def soft_apply_current_state(self, hlc_timestamp):
        try:
            self.driver.soft_apply(hcl=hlc_timestamp)
        except Exception as err:
            print(err)

        self.nonces.flush_pending()
        gc.collect()

    def make_tx_message(self, tx):
        hlc_timestamp = self.hlc_clock.get_new_hlc_timestamp()
        tx_hash = tx_hash_from_tx(tx=tx)

        signature = self.wallet.sign(f'{tx_hash}{hlc_timestamp}')

        return {
            'tx': tx,
            'hlc_timestamp': hlc_timestamp,
            'signature': signature,
            'sender': self.wallet.verifying_key
        }

    def update_block_db(self, block):
        # if self.testing:
        #    self.debug_stack.append({'method': 'update_block_db', 'block': self.current_height})
        # TODO Do we need to tdo this again? it was done in "soft_apply_current_state" which is run before this
        # self.driver.clear_pending_state()

        # Commit the state changes and nonces to the database

        storage.set_latest_block_hash(block['hash'], driver=self.driver)
        storage.set_latest_block_height(block['number'], driver=self.driver)

        self.new_block_processor.clean(self.get_current_height())

        self.driver.commit()

    def get_state_changes_from_block(self, block):
        tx_result = block.get('processed')
        return tx_result.get('state')

    def apply_state_changes_from_block(self, block):
        state_changes = block['processed'].get('state', [])
        hlc_timestamp = block['processed'].get('hlc_timestamp', None)

        if hlc_timestamp is None:
            hlc_timestamp = block.get('hlc_timestamp')

        for s in state_changes:
            if type(s['value']) is dict:
                s['value'] = convert_dict(s['value'])

            self.driver.set(s['key'], s['value'])

        self.soft_apply_current_state(hlc_timestamp=hlc_timestamp)
        self.driver.hard_apply(hlc=hlc_timestamp)

    async def hard_apply_block(self, processing_results):
        '''
        if self.testing:

            self.debug_stack.append({
                'system_time' :time.time(), 
                'method': 'hard_apply_block',
                'hlc_timestamp': hlc_timestamp
            })
        '''


        hlc_timestamp = processing_results.get('hlc_timestamp')

        next_block_num = self.current_block_height + 1

        prev_block = self.blocks.get_previous_block(v=self.current_block_height)

        # Get any blocks that have been commited that are later than this hlc_timestamp
        later_blocks = self.blocks.get_later_blocks(block_height=self.current_block_height, hlc_timestamp=hlc_timestamp)

        # If there are later blocks then we need to process them
        if len(later_blocks) > 0:
            try:
                await self.stop_main_processing_queue(force=True)
            except Exception as err:
                errors = err
                print(errors)
                pass

            # Get the block number of the block right after where we want to put this tx this will be the block number
            # for our new block
            next_block_num = later_blocks[0].get('number')
            prev_block = self.blocks.get_previous_block(v=later_blocks[0].get('number') - 1)

            new_block = block_from_tx_results(
                processing_results=processing_results,
                block_num=next_block_num,
                proofs=self.validation_queue.get_proofs_from_results(hlc_timestamp=hlc_timestamp),
                prev_block_hash=prev_block.get('hash')
            )

            for i in range(len(later_blocks)):
                if i is 0:
                    prev_block_in_list = new_block
                else:
                    prev_block_in_list = later_blocks[i - 1]

                later_blocks[i] = recalc_block_info(
                    block=later_blocks[i],
                    new_block_num=later_blocks[i].get('number') + 1,
                    new_prev_hash=prev_block_in_list.get('hash')
                )

            # Get all the writes that this new block will make to state
            new_block_writes = []
            new_block_state_changes = processing_results['tx_result'].get('state')

            for state_change in new_block_state_changes:
                new_block_writes.append(state_change.get('key'))

            # Apply the state changes from the block to the db
            self.apply_state_changes_from_block(new_block)

            # Store the new block in the block db
            self.blocks.store_block(new_block)

            # Emit a block reorg event

            # create a NEW_BLOCK_REORG_EVENT
            encoded_block = encode(new_block)
            encoded_block = json.loads(encoded_block)

            self.event_writer.write_event(Event(
                topics=[NEW_BLOCK_REORG_EVENT],
                data=encoded_block
            ))

            # Next we'll cycle through the later blocks and remove any keys from the new_block_writes list if they are
            # overwritten.  This is so when we reprocess we don't rerun a transaction that depended on a key we already
            # had the correct value for.
            for block in later_blocks:
                block_state_changes = self.get_state_changes_from_block(block=block)

                for state_change in block_state_changes:
                    state_key = state_change.get('key')
                    if state_key in new_block_writes:
                        new_block_writes.remove(state_key)

                # Apply the state changes for this block to the db
                self.apply_state_changes_from_block(block)

            # Re-save each block to the database
            for block in later_blocks:
                self.blocks.store_block(block)

                # create a NEW_BLOCK_REORG_EVENT
                encoded_block = encode(block)
                encoded_block = json.loads(encoded_block)

                self.event_writer.write_event(Event(
                    topics=[NEW_BLOCK_REORG_EVENT],
                    data=encoded_block
                ))

            # Set the current block hash and height
            self.update_block_db(block=later_blocks[-1])

            # if there are new keys that have been applied to state then we need to reassess everything we have
            # processed thus far
            if len(new_block_writes) > 0:
                self.reprocess_after_earlier_block(new_keys_list=new_block_writes)

            self.start_main_processing_queue()

        else:
            new_block = block_from_tx_results(
                processing_results=processing_results,
                block_num=next_block_num,
                proofs=self.validation_queue.get_proofs_from_results(hlc_timestamp=hlc_timestamp),
                prev_block_hash=prev_block.get('hash')
            )

            consensus_matches_me = self.validation_queue.consensus_matches_me(hlc_timestamp=hlc_timestamp)

            # Hard apply this hlc_timestamps state changes
            if hlc_timestamp in self.driver.pending_deltas and consensus_matches_me:
                self.driver.hard_apply(hlc_timestamp)
            else:
                self.apply_state_changes_from_block(new_block)


            # Store the block in the block db
            encoded_block = encode(new_block)
            encoded_block = json.loads(encoded_block)

            self.blocks.store_block(encoded_block)

            # Set the current block hash and height
            self.update_block_db(block=encoded_block)

            # create New Block Event
            self.event_writer.write_event(Event(
                topics=[NEW_BLOCK_EVENT],
                data=encoded_block
            ))

        # remove the processing results and read history from the main_processing queue memory
        self.main_processing_queue.prune_history(hlc_timestamp=hlc_timestamp)

        if self.testing:
            self.debug_processed_hlcs.append(hlc_timestamp)

        # Increment the internal block counter
        self.current_block_height += 1

        gc.collect()


# Re-processing CODE
    async def reprocess(self, tx):
        # make a copy of all the values before reprocessing, so we can compare transactions that are rerun
        pending_delta_history = deepcopy(self.driver.pending_deltas)
        self.log.debug(f"pending_delta_history: {pending_delta_history}")

        self.log.debug(f"Reprocessing {len(pending_delta_history.keys())} Transactions")

        # Get HLC of tx that needs to be run
        new_tx_hlc_timestamp = tx.get("hlc_timestamp")
        self.log.debug(f"new_tx_hlc_timestamp: {new_tx_hlc_timestamp}")

        # Get the read history of all transactions that were run
        changed_keys_list = []

        # Add the New HLC to the list of hlcs so we can process it in order
        pending_delta_items = list(pending_delta_history.keys())
        pending_delta_items.append(new_tx_hlc_timestamp)
        pending_delta_items.sort()

        # Check the read_history if all HLCs that were processed, in order of oldest to newest
        for index, read_history_hlc in enumerate(pending_delta_items):
            self.log.debug(f"read_history_hlc: {read_history_hlc}")

            # if this is the transaction we have to rerun,
            if read_history_hlc == new_tx_hlc_timestamp:
                self.log.debug(f"read_history_hlc: EQUALS")
                if self.testing:
                    self.debug_reprocessing_results[read_history_hlc] = {
                        'reprocess_type': 'run',
                        'sent_to_network': True
                    }
                try:
                    # rollback to this point
                    self.rollback_drivers(hlc_timestamp=new_tx_hlc_timestamp)

                    # Process the transaction
                    processing_results = self.main_processing_queue.process_tx(tx=tx)
                    self.soft_apply_current_state(hlc_timestamp=new_tx_hlc_timestamp)
                    changed_keys_list = list(deepcopy(self.driver.pending_deltas[new_tx_hlc_timestamp].get('writes')))
                    self.store_solution_and_send_to_network(processing_results=processing_results)
                    continue
                except Exception as err:
                    self.log.error(err)

            # if the hlc is less than the hlc we need to run then leave it alone, it won't need any changes
            if read_history_hlc < new_tx_hlc_timestamp:
                self.log.debug(f"read_history_hlc: LESS THAN")
                continue

            # If HLC is greater than rollback point check it for reprocessing
            if read_history_hlc > new_tx_hlc_timestamp:
                self.log.debug(f"read_history_hlc: GREATER THAN")
                try:
                    self.reprocess_hlc(
                        hlc_timestamp=read_history_hlc,
                        pending_deltas=pending_delta_history.get(read_history_hlc, {}),
                        changed_keys_list=changed_keys_list
                    )
                except Exception as err:
                    self.log.error(err)

    def reprocess_after_earlier_block(self, new_keys_list):
        # make a copy of all the values before reprocessing, so we can compare transactions that are rerun
        pending_delta_history = deepcopy(self.driver.pending_deltas)

        self.log.debug(f"Reprocessing {len(pending_delta_history.keys())} Transactions")

        # Get the read history of all transactions that were run
        changed_keys_list = new_keys_list

        # Get and sort the list of HLCs so we can process it in order
        pending_delta_items = list(self.driver.pending_deltas.keys())
        pending_delta_items.sort()

        # Check the read_history if all HLCs that were processed, in order of oldest to newest
        for index, read_history_hlc in enumerate(pending_delta_items):
            try:
                self.reprocess_hlc(
                    hlc_timestamp=read_history_hlc,
                    pending_deltas=pending_delta_history.get(read_history_hlc, {}),
                    changed_keys_list=changed_keys_list
                )
            except Exception as err:
                self.log.error(err)

    def reprocess_hlc(self, hlc_timestamp, pending_deltas, changed_keys_list):
        # Create a flag to determine there were any matching keys
        key_in_change_list = False
        prev_pending_deltas = pending_deltas

        # Get the keys that tx read from
        read_history_keys = list(prev_pending_deltas.get('reads', {}).keys())

        # Look at each key this hlc read and see if it was a key that was changed earlier either by the hlc
        # that triggered this reprocessing or due to reprocessing
        for read_key in read_history_keys:
            if read_key in changed_keys_list:
                # Flag that we matched a key
                key_in_change_list = True
                break

        if key_in_change_list:
            # Get the transaction info from the validation results queue
            recreated_tx_message = self.validation_queue.get_recreated_tx_message(hlc_timestamp)

            try:
                # Reprocess the transaction
                processing_results = self.main_processing_queue.process_tx(tx=recreated_tx_message)

                # Create flag to know if anything changes so we can later resend our new results to the
                # network
                re_send_to_network = False

                # Check if the previous run had any pending deltas
                pending_deltas_writes = prev_pending_deltas.get('writes', {})
                pending_writes = self.driver.pending_writes

                # FOR TESTING
                reprocess_type = ""

                # If there were no previous writes but reprocessing had writes then just add then all to
                # the changed_keys_list and flag to resend our results to the network
                if len(pending_deltas_writes) is 0 and len(pending_writes) > 0:
                    reprocess_type = 'no_deltas'

                    # Flag that we need to resend our results to the network
                    re_send_to_network = True

                    # Add all the keys from the pending_writes to the changed_keys_list
                    for pending_writes_key in pending_writes.keys():
                        if pending_writes_key not in changed_keys_list:
                            changed_keys_list.append(pending_writes_key)

                # If there WERE writes before AND reprocessing had no writes then add all the before
                # writes to the changed_keys_list and flag to resend our results to the network
                if len(pending_deltas_writes) > 0 and len(pending_writes) is 0:
                    reprocess_type = 'no_writes'

                    # Flag that we need to resend our results to the network
                    re_send_to_network = True

                    # Add all the keys from the pending_writes to the changed_keys_list
                    for pending_deltas_key in pending_deltas_writes.keys():
                        if pending_deltas_key not in changed_keys_list:
                            changed_keys_list.append(pending_deltas_key)

                # If there were writes previously and after reprocessing then compare then to see if
                # anything changed
                if len(pending_deltas_writes) > 0 and len(pending_writes) > 0:
                    reprocess_type = 'has_both'

                    # check the value of each key written during processing against the value of the
                    # previous run
                    for pending_writes_key, new_write_value in pending_writes.items():
                        has_changed = False
                        # Removed this value from the dict so we can see if there are leftovers afterwards
                        prev_write_deltas = pending_deltas_writes.pop(pending_writes_key, None)

                        if prev_write_deltas is None:
                            has_changed = True
                        else:
                            prev_write_value = prev_write_deltas[1]
                            if prev_write_value != new_write_value:
                                has_changed = True

                        if has_changed:
                            # Processing results produced changed results so add this key to the changed
                            # key list so we can check it against the reads of later hlcs in reprocessing
                            if pending_writes_key not in changed_keys_list:
                                changed_keys_list.append(pending_writes_key)

                            # Set flag to sent new results to the network
                            re_send_to_network = True

                    # Check if there are any pending deltas we didn't deal with. This is a situation where
                    # there were writes that happened previously and not during reprocessing
                    if len(pending_deltas_writes) > 0:
                        reprocess_type = 'has_extra_deltas'

                        # Add all the the extra keys to the changed key list because they will now be None
                        # and could effect transactions later on
                        for pending_deltas_key in pending_deltas_writes.keys():
                            changed_keys_list.append(pending_deltas_key)

                # If there were changes to the writes above then we need to re-communicate our results to the
                # rest of the nodes
                if re_send_to_network:
                    # Processing results produced new results so add this key to the changed
                    # key list so we can check it against the reads of later hlcs in reprocessing
                    self.log.debug({"RESENDING_TO_NETWORK": processing_results})
                    self.store_solution_and_send_to_network(processing_results=processing_results)

                self.log.debug({
                        'reprocess_type': reprocess_type,
                        'sent_to_network': re_send_to_network
                    })

                if self.testing:
                    self.debug_reprocessing_results[hlc_timestamp] = {
                        'reprocess_type': reprocess_type,
                        'sent_to_network': re_send_to_network
                    }

            except Exception as err:
                self.log.error(err)
        else:
            if self.testing:
                self.debug_reprocessing_results[hlc_timestamp] = {
                    'reprocess_type': "no_match",
                    'sent_to_network': False
                }

            self.log.debug({
                    'reprocess_type': "no_match",
                    'sent_to_network': False
                })

            for pending_delta_key, pending_delta_value in pending_deltas.items():
                self.driver.pending_writes[pending_delta_key] = pending_delta_value[1]

        self.soft_apply_current_state(hlc_timestamp=hlc_timestamp)

    def rollback_drivers(self, hlc_timestamp):
        # Roll back the current state to the point of the last block consensus
        self.log.debug(f"Length of Pending Deltas BEFORE {len(self.driver.pending_deltas.keys())}")
        self.log.debug(f"rollback to hlc_timestamp: {hlc_timestamp}")

        if hlc_timestamp is None:
            # Returns to disk state which should be whatever it was prior to any write sessions
            self.driver.cache.clear()
            self.driver.reads = set()
            self.driver.pending_writes.clear()
            self.driver.pending_deltas.clear()
        else:
            to_delete = []
            for _hlc, _deltas in sorted(self.driver.pending_deltas.items())[::-1]:
                # Clears the current reads/writes, and the reads/writes that get made when rolling back from the
                # last HLC
                self.driver.reads = set()
                self.driver.pending_writes.clear()


                if _hlc < hlc_timestamp:
                    self.log.debug(f"{_hlc} is less than {hlc_timestamp}, breaking!")
                    # if we are less than the HLC then top processing anymore, this is our rollback point
                    break
                else:
                    # if we are still greater than or equal to then mark this as delete and rollback its changes
                    to_delete.append(_hlc)
                    # Run through all state changes, taking the second value, which is the post delta
                    for key, delta in _deltas['writes'].items():
                        # self.set(key, delta[0])
                        self.driver.cache[key] = delta[0]

            # Remove the deltas from the set
            self.log.debug(to_delete)
            [self.driver.pending_deltas.pop(key) for key in to_delete]

        #self.driver.rollback(hlc=hlc_timestamp)

        self.log.debug(f"Length of Pending Deltas AFTER {len(self.driver.pending_deltas.keys())}")

    def reset_last_hlc_processed(self):
        self.last_processed_hlc = self.validation_queue.last_hlc_in_consensus

    # Put into 'super driver'
    def get_block_by_hlc(self, hlc_timestamp):
        return self.blocks.get_block(v=hlc_timestamp)

    # Put into 'super driver'
    def get_block_by_number(self, block_number):
        return self.blocks.get_block(v=block_number)

    def make_constitution(self):
        return {
            'masternodes': self.network.get_masternode_peers(),
            'delegates': self.network.get_delegate_peers()
        }

    def seed_genesis_contracts(self):
        self.log.info('Setting up genesis contracts.')
        sync.setup_genesis_contracts(
            initial_masternodes=self.constitution['masternodes'],
            initial_delegates=self.constitution['delegates'],
            client=self.client,
            filename=self.genesis_path + '/genesis.json',
            root=self.genesis_path
        )

    def should_process(self, block):
        try:
            pass
            # self.log.info(f'Processing block #{block.get("number")}')
        except:
            self.log.error('Malformed block :(')
            return False
        # Test if block failed immediately
        if block == {'response': 'ok'}:
            return False

        if block['hash'] == 'f' * 64:
            self.log.error('Failed Block! Not storing.')
            return False

        return True

    def update_cache_state(self, results):
        # TODO This should be the actual cache write but it's HDD for now
        self.driver.clear_pending_state()

        storage.update_state_with_transaction(
            tx=results['transactions'][0],
            driver=self.driver,
            nonces=self.nonces
        )

    # Put into 'super driver'
    def get_current_height(self):
        return storage.get_latest_block_height(self.driver)

    # Put into 'super driver'
    def get_current_hash(self):
        return storage.get_latest_block_hash(self.driver)

    # Put into 'super driver'
    def get_latest_block(self):
        latest_block_num = self.get_current_height()
        block = self.blocks.get_block(v=latest_block_num)
        return block

    def get_last_processed_hlc(self):
        return self.last_processed_hlc

    def get_last_hlc_in_consensus(self):
        return self.validation_queue.last_hlc_in_consensus

    def is_next_block(self, previous_hash):
        self.log.debug({
            'current_hash': self.get_consensus_hash(),
            'previous_hash': previous_hash
        })
        return previous_hash == self.get_consensus_hash()

    def check_if_already_has_consensus(self, hlc_timestamp):
        return self.validation_queue.hlc_has_consensus(hlc_timestamp=hlc_timestamp)


    '''
    async def catchup(self, mn_seed, mn_vk):
        # Get the current latest block stored and the latest block of the network
        self.log.info('Running catchup.')
        current = self.current_height
        latest = await get_latest_block_height(
            ip=mn_seed,
            vk=mn_vk,
            wallet=self.wallet,
            ctx=self.ctx
        )

        self.log.info(f'Current block: {current}, Latest available block: {latest}')

        if latest == 0 or latest is None or type(latest) == dict:
            self.log.info('No need to catchup. Proceeding.')
            return

        # Increment current by one. Don't count the genesis block.
        if current == 0:
            current = 1

        # Find the missing blocks process them
        for i in range(current, latest + 1):
            block = None
            while block is None:
                block = await get_block(
                    block_num=i,
                    ip=mn_seed,
                    vk=mn_vk,
                    wallet=self.wallet,
                    ctx=self.ctx
                )
            self.process_new_block(block)

        # Process any blocks that were made while we were catching up
        while len(self.new_block_processor.q) > 0:
            block = self.new_block_processor.q.pop(0)
            self.process_new_block(block)
    '''