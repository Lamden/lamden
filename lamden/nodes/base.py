import asyncio
import copy
import gc
import hashlib
import json
import random
import time
import uvloop

from copy import deepcopy
from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver
from contracting.db.encoder import convert_dict, encode

from lamden import storage, router, upgrade, contracts
from lamden.peer import Peer
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

from typing import List

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

    is_masternode = verifying_key in masternodes.keys()
    is_delegate = verifying_key in delegates.keys()

    assert is_masternode or is_delegate, 'You are not in the constitution!'

class Node:
    def __init__(self, socket_base,  wallet, constitution: dict, bootnodes={}, blocks=None,
                 driver=None, delay=None, debug=True, testing=False, seed=None, bypass_catchup=False, node_type=None,
                 genesis_path=contracts.__path__[0], consensus_percent=None,
                 nonces=None, parallelism=4, should_seed=True, metering=False, tx_queue=None,
                 socket_ports=None, reconnect_attempts=60):

        self.consensus_percent = consensus_percent or 51
        self.processing_delay_secs = delay or {
            'base': 1,
            'self': 0.5
        }
        # amount of consecutive out of consensus solutions we will tolerate from out of consensus nodes
        self.tx_queue = tx_queue if tx_queue is not None else FileQueue()
        self.pause_tx_queue_checking = False

        self.driver = driver if driver is not None else ContractDriver()
        self.nonces = nonces if nonces is not None else storage.NonceStorage()
        self.event_writer = EventWriter()

        self.seed = seed

        self.blocks = blocks if blocks is not None else storage.BlockStorage()
        self.current_block_height = 0

        self.log = get_logger('Base')
        self.debug = debug
        self.testing = testing

        self.debug_stack = []
        self.debug_processed_hlcs = []
        self.debug_processing_results = []
        self.debug_reprocessing_results = {}
        self.debug_blocks_processed = []
        self.debug_blocks_hard_applied = []
        self.debug_timeline = []
        self.debug_sent_solutions = []
        self.debug_last_checked_main = time.time()
        self.debug_last_checked_val = time.time()
        self.debug_loop_counter = {
            'main': 0,
            'validation': 0,
            'file_check': 0
        }
        self.last_printed_loop_counter = time.time()

        self.log.propagate = debug
        self.socket_base = socket_base
        self.wallet = wallet
        self.hlc_clock = HLC_Clock()

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
            wallet=wallet,
            socket_ports=socket_ports,
            driver=self.driver,
            block_storage=self.blocks
        )

        # Number of core / processes we push to
        self.parallelism = parallelism

        self.new_block_processor = NewBlock(driver=self.driver)

        self.main_processing_queue = processing_queue.TxProcessingQueue(
            testing=self.testing,
            debug=self.debug,
            driver=self.driver,
            client=self.client,
            wallet=self.wallet,
            metering=metering,
            hlc_clock=self.hlc_clock,
            processing_delay=lambda: self.processing_delay_secs,                        # Abstract
            get_last_hlc_in_consensus=self.get_last_hlc_in_consensus,                   # Abstract
            stop_node=self.stop,
            reprocess=self.reprocess,
            check_if_already_has_consensus=self.check_if_already_has_consensus,         # Abstract
            pause_all_queues=self.pause_validation_queue,
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
            stop_node=self.stop
        )

        self.total_processed = 0
        # how long to hold items in queue before processing

        self.work_validator = work.WorkValidator(
            wallet=wallet,
            main_processing_queue=self.main_processing_queue,
            hlc_clock=self.hlc_clock,
            get_last_processed_hlc=self.get_last_processed_hlc,
            stop_node=self.stop,
            driver=self.driver,
            nonces=self.nonces
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

        self.running = False
        self.started = False
        self.upgrade = False

        self.last_minted_block = None

        self.bypass_catchup = bypass_catchup

        self.reconnect_attempts = reconnect_attempts

        self.check_main_processing_queue_task = None
        self.check_validation_queue_task = None

    ''' NAH
    def __del__(self):
        self.network.stop()
        self.system_monitor.stop()
    '''

    @property
    def node_type(self) -> str:
        return self.upgrade_manager.node_type

    async def start(self):
        try:
            # Start running
            self.running = True

            if self.debug:
                asyncio.ensure_future(self.system_monitor.start(delay_sec=120))
                asyncio.ensure_future(self.debug_print_loop_counter())

            self.network.start()
            await self.network.starting()

            if self.should_seed:
                await self.start_new_network()
                print("STARTED NODE")
            else:
                await self.join_existing_network()
                print("STARTED NODE")

        except Exception as err:
            self.running = False
            self.log.error(err)
            print(err)

            await asyncio.sleep(1)
            await self.stop()

    async def stop(self):
        self.log.error("!!!!!! STOPPING NODE !!!!!!")

        self.running = False
        await self.cancel_checking_all_queues()

        await self.network.stop()
        self.system_monitor.stop()
        await self.system_monitor.stopping()

        self.started = False

        self.log.error("!!!!!! STOPPED NODE !!!!!!")

    async def start_new_network(self):
        '''
            self.bootnodes is a {vk:ip} dict
        '''

        for vk, ip in self.bootnodes.items():
            self.log.info({"vk": vk, "ip": ip})

            if vk != self.wallet.verifying_key:
                print(f'Attempting to connect to peer "{vk}" @ {ip}')
                self.log.info(f'Attempting to connect to peer "{vk}" @ {ip}')

                # Use it to boot up the network
                self.network.connect_peer(
                    ip=ip,
                    vk=vk
                )

        self.log.info("Attempting to connect to all peers in constitution...")
        await self.network.connected_to_all_peers()

        self.driver.clear_pending_state()

        self.start_validation_queue_task()
        self.start_main_processing_queue_task()

        self.started = True

    async def join_existing_network(self):
        bootnode = None

        # Connect to a node on the network using the bootnode list
        for vk, ip in self.bootnodes.items():
            print(f'Attempting to connect to bootnode "{vk}" @ {ip}')
            self.log.info(f'Attempting to connect to bootnode "{vk}" @ {ip}')

            if vk != self.wallet.verifying_key:
                self.network.authorize_peer(peer_vk=vk)
                try:
                    # Use it to boot up the network
                    self.network.connect_to_bootnode(
                        ip=ip,
                        vk=vk
                    )
                except Exception as err:
                    print(f'Exception raised while attempting connection to "{vk}" @ {ip}')
                    print(err)
                    self.log.error(f'Exception raised while attempting connection to "{vk}" @ {ip}')
                    self.log.error(err)


                bootnode = self.network.get_peer(vk=vk)

                connection_attempts = 0
                sleep_for = 5

                while not bootnode.is_connected:
                    connection_attempts += 1

                    if connection_attempts > self.reconnect_attempts:
                        bootnode = None
                        self.network.revoke_peer_access(peer_vk=vk)
                        self.network.remove_peer(peer_vk=vk)

                        break

                    self.log.info(f'Attempt {connection_attempts}/attempts failed to connect. Trying again in {sleep_for} seconds.')
                    await asyncio.sleep(sleep_for)

        if bootnode is None:
            print("Could not connect to any bootnodes!")
            print(self.bootnodes)
            self.log.error("Could not connect to any bootnodes!")
            self.log.error(self.bootnodes)

            raise Exception("Could not connect to any bootnodes!")

        # Get the rest of the nodes from our bootnode
        response = await bootnode.get_network_map()

        try:
            network_map = response.get('network_map')
            if not network_map:
                raise AttributeError()
        except:
            print(f"Node {bootnode.get('vk')} failed to provided a node list! Exiting..")
            print(response)
            self.log.error(f"Node {bootnode.get('vk')} failed to provided a node list! Exiting..")
            self.log.error(response)

            raise Exception(f"Node {bootnode.get('vk')} failed to provided a node list! Exiting..")

        # Create a constitution file
        self.constitution = self.network.network_map_to_constitution(network_map=network_map)

        # Create genesis contracts
        self.seed_genesis_contracts()

        # Connect to all nodes in the network
        for node_info in self.network.network_map_to_node_list(network_map=network_map):
            vk = node_info.get('vk')
            ip = node_info.get('ip')

            print({"vk": vk, "ip": ip})
            self.log.info({"vk": vk, "ip": ip})

            self.network.refresh_approved_peers_in_cred_provider()

            if vk != self.wallet.verifying_key:
                # connect to peer
                self.network.connect_peer(
                    ip=ip,
                    vk=vk
                )

        await self.network.connected_to_all_peers()

        needs_catchup = self.network.get_highest_peer_block() > 0
        if needs_catchup:
            # Run an initial catchup to get as many blocks as we can
            await self.catchup()

            # Run a continuous catchup to get any blocks that have been minted during the initial catchup.
            await self.catchup_continuous(block_threshold=10)

            # Start the validation queue so we start accepting block results
            self.start_validation_queue_task()

            # Now start catching up to minting of blocks from validation queue
            await self.catchup_to_validation_queue(catchup_starting_height=self.get_current_height())
        else:
            # Start the validation queue so we start accepting block results
            self.start_validation_queue_task()


        self.driver.clear_pending_state()

        # Start the processing queue
        self.start_main_processing_queue_task()

        self.started = True

    async def catchup(self):
        # Get the current latest block stored and the latest block of the network
        self.log.info('Running catchup.')

        try:
            catchup_peers = self.network.get_all_connected_peers()

            if len(catchup_peers) == 0:
                self.log.error(f'No peers available for catchup!')
                await self.stop()
            else:
                highest_peer_block = self.network.get_highest_peer_block()
                await self.catchup_get_blocks(catchup_peers=catchup_peers, catchup_stop_block=highest_peer_block + 1)
        except Exception as err:
            self.log.error(err)
            print(err)
            await self.stop()

    async def catchup_continuous(self, block_threshold: int):
        '''
            This will run till the node has caught up within the block_threshold number of blocks.
            After each iteration of catchup_blocks we will see the new block height of each peer and if we are not
            within the supplied block_threshold we run it again.
        '''
        await self.network.refresh_peer_block_info()

        try:
            while (self.network.get_highest_peer_block() - self.get_current_height()) > block_threshold:
                catchup_peers = self.network.get_all_connected_peers()

                if len(catchup_peers) == 0:
                    raise Exception('No peers available for catchup!')
                else:
                    highest_peer_block = self.network.get_highest_peer_block()
                    await self.catchup_get_blocks(catchup_peers=catchup_peers, catchup_stop_block=highest_peer_block)

                await self.network.refresh_peer_block_info()

        except Exception as err:
            self.log.error(err)
            await self.stop()

    async def catchup_to_validation_queue(self, catchup_starting_height: int) -> None:
        '''
            This will get blocks upto the point that we don't need them because we are producing them from the
            validation queue
        '''

        self.log.info('Waiting for new block to be minted from validation queue.')
        while self.last_minted_block is None:
            await asyncio.sleep(0)

        first_block_minted = self.last_minted_block.get("number")

        # if we have the block right before the block we just minted then return
        if (catchup_starting_height + 1) == first_block_minted:
            return
        else:
            catchup_peers = self.network.get_all_connected_peers()
            catchup_peers_with_block = list(filter(lambda x: x.latest_block_number >= first_block_minted - 1, catchup_peers))

            await self.catchup_get_blocks(
                catchup_peers=catchup_peers_with_block,
                catchup_stop_block=first_block_minted
            )

        self.validation_queue.pause()

        current = self.get_current_height()

        for i in range(current - first_block_minted):
            block = self.blocks.get_block(v=first_block_minted + 1)
            self.apply_state_changes_from_block(block=encode(block))

        self.validation_queue.start()


    async def catchup_get_blocks(self, catchup_peers: List[Peer], catchup_stop_block: int):
        current = self.get_current_height()

        while current < catchup_stop_block:
            next_block_num = current + 1

            catchup_peers = list(filter(lambda x: x.latest_block_number >= next_block_num, catchup_peers))
            block_catchup_peers = copy.copy(catchup_peers)

            response = None
            while len(block_catchup_peers) > 0:
                catchup_peer = random.choice(block_catchup_peers)
                response = await catchup_peer.get_block(block_num=next_block_num)

                if response is None:
                    block_catchup_peers = list(filter(lambda x: x.local_vk != catchup_peer.local_vk, block_catchup_peers))
                else:
                    break

            if type(response) is dict:
                new_block = response.get("block_info")
                self.log.info(new_block)

                if new_block:
                    block_number = new_block.get('number')
                    if block_number == next_block_num:
                        # Apply state to DB
                        self.apply_state_changes_from_block(block=new_block)

                        # Store the block in the block db
                        encoded_block = encode(new_block)
                        encoded_block = json.loads(encoded_block)

                        self.blocks.store_block(block=deepcopy(encoded_block))

                        # Set the current block hash and height
                        self.update_block_db(block=encoded_block)

                        #create New Block Event
                        self.event_writer.write_event(Event(
                            topics=[NEW_BLOCK_EVENT],
                            data=encoded_block
                        ))
                        self.current_block_height = block_number
                    else:
                        self.log.error("Incorrect Block Number response in catchup!")
                        print("Incorrect Block Number response in catchup!")
            else:
                self.log.error(f"Cannot find block {next_block_num} on any node. Skipping...")
                print(f"Cannot find block {next_block_num} on node on any node. Skipping...")

            current = next_block_num

    def start_main_processing_queue_task(self):
        self.log.info('STARTING MAIN PROCESSING QUEUE')
        self.check_main_processing_queue_task = asyncio.ensure_future(self.check_main_processing_queue())

    def start_validation_queue_task(self):
        self.log.info('STARTING VALIDATION QUEUE')
        self.check_validation_queue_task = asyncio.ensure_future(self.check_validation_queue())

    async def cancel_checking_all_queues(self):
        self.log.info("!!!!!! STOPPING ALL QUEUES !!!!!!")
        self.log.debug(f'NODE RUNNING: {self.running}')

        self.main_processing_queue.stop()
        self.validation_queue.stop()

        while self.check_main_processing_queue_task and not self.check_main_processing_queue_task.done():
            await asyncio.sleep(0)
        self.log.info("!!!!!! main_processing_queue STOPPED !!!!!!")

        while self.check_validation_queue_task and not self.check_validation_queue_task.done():
            await asyncio.sleep(0)
        self.log.info("!!!!!! validation_queue STOPPED !!!!!!")

    async def pause_main_processing_queue(self):
        self.log.info("!!!!!! PAUSING main_processing_queue !!!!!!")
        self.main_processing_queue.pause()
        await self.main_processing_queue.pausing()
        self.log.info("!!!!!! main_processing_queue PAUSED !!!!!!")

    async def pause_validation_queue(self):
        self.log.info("!!!!!! PAUSING validation_queue !!!!!!")
        self.validation_queue.pause()
        await self.validation_queue.pausing()
        self.log.info("!!!!!! validation_queue PAUSED !!!!!!")

    def unpause_all_queues(self):
        self.log.info("!!!!!! RESUMING ALL QUEUES !!!!!!")
        self.main_processing_queue.unpause()
        self.validation_queue.unpause()
        self.log.info(f"main_processing_queue paused: {self.main_processing_queue.paused}")
        self.log.info(f"validation_queue paused: {self.validation_queue.paused}")

    async def pause_all_queues(self):
        self.log.info("!!!!!! PAUSING ALL QUEUES !!!!!!")
        await self.pause_main_processing_queue()
        await self.pause_validation_queue()

    def pause_tx_queue(self):
        self.pause_tx_queue_checking = True

    def unpause_tx_queue(self):
        self.pause_tx_queue_checking = False

    async def check_tx_queue(self):
        while self.running and not self.pause_tx_queue_checking:
            if len(self.tx_queue) > 0:
                self.log.debug("Calling Check TX File Queue")
                tx_from_file = self.tx_queue.pop(0)
                # TODO sometimes the tx info taken off the filequeue is None, investigate
                self.log.info(f'GOT TX FROM FILE {tx_from_file}')
                if tx_from_file is not None:
                    tx_message = self.make_tx_message(tx=tx_from_file)

                    # send the tx to the rest of the network
                    asyncio.ensure_future(self.network.publisher.async_publish(topic_str=WORK_SERVICE, msg_dict=tx_message))

                    # add this tx the processing queue so we can process it
                    self.main_processing_queue.append(tx=tx_message)

            self.debug_loop_counter['file_check'] = self.debug_loop_counter['file_check'] + 1
            await asyncio.sleep(0)

    async def check_main_processing_queue(self):
        self.main_processing_queue.start()

        while self.main_processing_queue.running:
            if len(self.main_processing_queue) > 0 and self.main_processing_queue.active:
                self.main_processing_queue.start_processing()
                await self.process_main_queue()
                self.main_processing_queue.stop_processing()

            self.debug_loop_counter['main'] = self.debug_loop_counter['main'] + 1
            await asyncio.sleep(0)

        self.log.info(f'Exited Check Main Processing Queue.')

    async def check_validation_queue(self):
        self.validation_queue.start()

        while self.validation_queue.running:
            if len(self.validation_queue.validation_results) > 0 and self.validation_queue.active:
                if not self.validation_queue.checking:
                    #self.log.debug(f"Calling Check Validation Queue with a Lenght of {len(self.validation_queue)}")
                    self.validation_queue.start_processing()
                    # TODO Alter this method to process just the earliest HLC
                    await self.validation_queue.process_next()
                    self.validation_queue.stop_processing()

            self.debug_loop_counter['validation'] = self.debug_loop_counter['validation'] + 1
            await asyncio.sleep(0)

        self.log.info(f'Exited Check Validation Queue.')

    async def process_main_queue(self):
        try:
            processing_results = await self.main_processing_queue.process_next()

            if processing_results and self.running:
                hlc_timestamp = processing_results.get('hlc_timestamp')
                self.soft_apply_current_state(hlc_timestamp=hlc_timestamp)

                if self.testing:
                    self.debug_processing_results.append(processing_results)

                if hlc_timestamp <= self.get_last_hlc_in_consensus():
                    block = self.blocks.get_block(v=hlc_timestamp)
                    my_result_hash = tx_result_hash_from_tx_result_object(
                        tx_result=processing_results['tx_result'],
                        hlc_timestamp=hlc_timestamp
                    )
                    block_result_hash = block['processed']['hash']

                    if my_result_hash != block_result_hash:
                        await self.reprocess(tx=processing_results['tx_result']['transaction'])
                else:
                    self.store_solution_and_send_to_network(processing_results=processing_results)

        except Exception as err:
            self.log.error(err)

    async def debug_print_loop_counter(self):
        if self.last_printed_loop_counter - time.time() > 30:
            if not self.running:
                return
            self.log.debug({'debug_loop_counter': self.debug_loop_counter})
            self.last_printed_loop_counter = time.time()

            await asyncio.sleep(5)


    def store_solution_and_send_to_network(self, processing_results):
        self.send_solution_to_network(processing_results=processing_results)

        processing_results = json.loads(encode(processing_results))

        processing_results['proof']['tx_result_hash'] = tx_result_hash_from_tx_result_object(
            tx_result=processing_results['tx_result'],
            hlc_timestamp=processing_results['hlc_timestamp']
        )

        self.validation_queue.append(
            processing_results=processing_results
        )

    def send_solution_to_network(self, processing_results):
        asyncio.ensure_future(self.network.publisher.async_publish(topic_str=CONTENDER_SERVICE, msg_dict=processing_results))

    def soft_apply_current_state(self, hlc_timestamp):
        try:
            self.driver.soft_apply(hcl=hlc_timestamp)
            gc.collect()
        except Exception as err:
            self.log.error(err)

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

        # NOTE: write it directly to disk.
        self.driver.driver.set(storage.LATEST_BLOCK_HASH_KEY, block['hash'])
        self.driver.driver.set(storage.LATEST_BLOCK_HEIGHT_KEY, block['number'])

        self.new_block_processor.clean(self.get_current_height())

        # NOTE(for Jeff): we shouldn't do this. what if there are pending writes
        # in driver.cache from a different HLC & not related to this block?
        # this line prevents 'test_network_mixed_tx_set_group__throughput'
        # from passing in a way that nodes aren't able to reach consensus at some point.
        #self.driver.commit()

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

        if processing_results is None:
            raise AttributeError('Processing Results are NONE')

        hlc_timestamp = processing_results.get('hlc_timestamp')

        next_block_num = self.current_block_height + 1

        prev_block = self.blocks.get_previous_block(v=self.current_block_height)

        # Get any blocks that have been commited that are later than this hlc_timestamp
        later_blocks = self.blocks.get_later_blocks(block_height=self.current_block_height, hlc_timestamp=hlc_timestamp)

        # If there are later blocks then we need to process them
        if len(later_blocks) > 0:
            try:
                await self.pause_main_processing_queue()
            except Exception as err:
                errors = err
                print(errors)
                pass

            # Get the block number of the block right after where we want to put this tx this will be the block number
            # for our new block
            next_block_num = later_blocks[0].get('number')
            prev_block = self.blocks.get_previous_block(v=next_block_num - 1)

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
            self.update_last_minted_block(new_minted_block=later_blocks[-1])

            # if there are new keys that have been applied to state then we need to reassess everything we have
            # processed thus far
            if len(new_block_writes) > 0:
                self.reprocess_after_earlier_block(new_keys_list=new_block_writes)

            self.start_main_processing_queue_task()

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

            self.blocks.store_block(copy.copy(encoded_block))

            # Set the current block hash and height
            self.update_block_db(block=encoded_block)

            self.update_last_minted_block(new_minted_block=new_block)

            # create New Block Event
            self.event_writer.write_event(Event(
                topics=[NEW_BLOCK_EVENT],
                data=encoded_block
            ))

        # remove the processing results and read history from the main_processing queue memory
        self.main_processing_queue.prune_history(hlc_timestamp=hlc_timestamp)

        self.log.info(f'[HARD APPLY] {new_block.get("number")}')

        # Increment the internal block counter
        self.current_block_height += 1

        gc.collect()

# Re-processing CODE
    async def reprocess(self, tx):
        # make a copy of all the values before reprocessing, so we can compare transactions that are rerun
        pending_delta_history = deepcopy(self.driver.pending_deltas)

        self.log.debug(f"Reprocessing {len(pending_delta_history.keys())} Transactions")

        # Get HLC of tx that needs to be run
        new_tx_hlc_timestamp = tx.get("hlc_timestamp")

        # Get the read history of all transactions that were run
        changed_keys_list = []

        # Add the New HLC to the list of hlcs so we can process it in order
        pending_delta_items = list(pending_delta_history.keys())
        pending_delta_items.append(new_tx_hlc_timestamp)
        pending_delta_items.sort()

        # Check the read_history if all HLCs that were processed, in order of oldest to newest
        for index, read_history_hlc in enumerate(pending_delta_items):

            # if this is the transaction we have to rerun,
            if read_history_hlc == new_tx_hlc_timestamp:
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
                continue

            # If HLC is greater than rollback point check it for reprocessing
            if read_history_hlc > new_tx_hlc_timestamp:
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

                # If there were no previous writes but reprocessing had writes then just add then all to
                # the changed_keys_list and flag to resend our results to the network
                if len(pending_deltas_writes) is 0 and len(pending_writes) > 0:
                    # Flag that we need to resend our results to the network
                    re_send_to_network = True

                    # Add all the keys from the pending_writes to the changed_keys_list
                    for pending_writes_key in pending_writes.keys():
                        if pending_writes_key not in changed_keys_list:
                            changed_keys_list.append(pending_writes_key)

                # If there WERE writes before AND reprocessing had no writes then add all the before
                # writes to the changed_keys_list and flag to resend our results to the network
                if len(pending_deltas_writes) > 0 and len(pending_writes) is 0:

                    # Flag that we need to resend our results to the network
                    re_send_to_network = True

                    # Add all the keys from the pending_writes to the changed_keys_list
                    for pending_deltas_key in pending_deltas_writes.keys():
                        if pending_deltas_key not in changed_keys_list:
                            changed_keys_list.append(pending_deltas_key)

                # If there were writes previously and after reprocessing then compare then to see if
                # anything changed
                if len(pending_deltas_writes) > 0 and len(pending_writes) > 0:

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

            except Exception as err:
                self.log.error(err)
        else:
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

        self.log.debug(f"Length of Pending Deltas AFTER {len(self.driver.pending_deltas.keys())}")

    def update_last_minted_block(self, new_minted_block):
        if self.last_minted_block is None:
            self.last_minted = new_minted_block
        else:
            last_minted_hlc = self.last_minted_block.get("hlc_timestamp", '0')
            new_minted_hlc = new_minted_block.get("hlc_timestamp")
            if new_minted_hlc > last_minted_hlc:
                self.last_minted = new_minted_block

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

        self.log.info(f'Initial Masternodes: {self.constitution["masternodes"]}')
        self.log.info(f'Initial Delegates: {self.constitution["delegates"]}')

        sync.setup_genesis_contracts(
            initial_masternodes=self.constitution['masternodes'],
            initial_delegates=self.constitution['delegates'],
            client=self.client,
            filename=self.genesis_path + '/genesis.json',
            root=self.genesis_path
        )

        self.driver.commit()

        masternodes = self.driver.get_var(contract='masternodes', variable='S', arguments=['members'])
        delegates = self.driver.get_var(contract='delegates', variable='S', arguments=['members'])

        self.log.info(f'Masternode Members: {masternodes}')
        self.log.info(f'Delegate Members: {delegates}')

        print('done')

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
        return self.main_processing_queue.last_processed_hlc

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
