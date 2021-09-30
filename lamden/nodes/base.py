import asyncio
import gc
import hashlib
import json
import time
import uvloop
import zmq.asyncio

from copy import deepcopy
from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, encode
from contracting.db.encoder import convert_dict
from contracting.execution.executor import Executor
from lamden import storage, router, rewards, upgrade, contracts
from lamden.contracts import sync
from lamden.crypto.wallet import Wallet
from lamden.logger.base import get_logger
from lamden.new_sockets import Network
from lamden.nodes import block_contender, system_usage
from lamden.nodes import work, processing_queue, validation_queue
from lamden.nodes.filequeue import FileQueue
from lamden.nodes.hlc import HLC_Clock
from lamden.crypto.canonical import tx_hash_from_tx, block_from_tx_results, recalc_block_info

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

BLOCK_SERVICE = 'catchup'
NEW_BLOCK_SERVICE = 'new_blocks'
WORK_SERVICE = 'work'
CONTENDER_SERVICE = 'contenders'

DB_CURRENT_BLOCK_HEIGHT = '_current_block_height'
DB_CURRENT_BLOCK_HASH = '_current_block_hash'
GET_BLOCK = 'get_block'
GET_HEIGHT = 'get_height'


async def get_latest_block_height(wallet: Wallet, vk: str, ip: str, ctx: zmq.asyncio.Context):
    msg = {
        'name': GET_HEIGHT,
        'arg': ''
    }

    response = await router.secure_request(
        ip=ip,
        vk=vk,
        wallet=wallet,
        service=BLOCK_SERVICE,
        msg=msg,
        ctx=ctx,
    )

    return response


async def get_block(block_num: int, wallet: Wallet, vk: str, ip: str, ctx: zmq.asyncio.Context):
    msg = {
        'name': GET_BLOCK,
        'arg': block_num
    }

    response = await router.secure_request(
        ip=ip,
        vk=vk,
        wallet=wallet,
        service=BLOCK_SERVICE,
        msg=msg,
        ctx=ctx,
    )

    return response

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
    def __init__(self, socket_base, ctx: zmq.asyncio.Context, wallet, constitution: dict, bootnodes={}, blocks=storage.BlockStorage(),
                 driver=ContractDriver(), delay=None, debug=True, testing=False, seed=None, bypass_catchup=False, node_type=None,
                 genesis_path=contracts.__path__[0], reward_manager=rewards.RewardManager(), consensus_percent=None,
                 nonces=storage.NonceStorage(), parallelism=4, should_seed=True, metering=False, tx_queue=FileQueue()):

        self.consensus_percent = consensus_percent or 51
        self.processing_delay_secs = delay or {
            'base': 0.75,
            'self': 0.75
        }
        # amount of consecutive out of consensus solutions we will tolerate from out of consensus nodes
        self.max_peer_strikes = 5
        self.rollbacks = []
        self.tx_queue = tx_queue

        self.driver = driver
        self.nonces = nonces

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

        self.log.propagate = debug
        self.socket_base = socket_base
        self.wallet = wallet
        self.hlc_clock = HLC_Clock()
        self.last_processed_hlc = self.hlc_clock.get_new_hlc_timestamp()
        self.ctx = ctx

        self.system_monitor = system_usage.SystemUsage()

        self.genesis_path = genesis_path

        self.client = ContractingClient(
            driver=self.driver,
            submission_filename=genesis_path + '/submission.s.py'
        )

        self.bootnodes = bootnodes
        self.constitution = constitution

        if should_seed:
            self.seed_genesis_contracts()
        # self.socket_authenticator = authentication.SocketAuthenticator(
        #     bootnodes=self.bootnodes, ctx=self.ctx, client=self.client
        # )

        self.upgrade_manager = upgrade.UpgradeManager(client=self.client, wallet=self.wallet, node_type=node_type)
        '''
        self.router = router.Router(
            socket_id=socket_base,
            ctx=self.ctx,
            wallet=wallet,
            secure=True
        )
        
        self.network = network.Network(
            wallet=wallet,
            ip_string=socket_base,
            ctx=self.ctx,
            router=self.router
        )
        '''

        # wallet: Wallet, ctx: zmq.Context, socket_id

        self.network = Network(
            debug=self.debug,
            testing=self.testing,
            wallet=wallet,
            socket_id=socket_base,
            max_peer_strikes=self.max_peer_strikes,
            ctx=self.ctx,
        )

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver, metering=metering)
        self.reward_manager = reward_manager

        self.new_block_processor = NewBlock(driver=self.driver)
        # self.router.add_service(NEW_BLOCK_SERVICE, self.new_block_processor)

        self.main_processing_queue = processing_queue.TxProcessingQueue(
            testing=self.testing,
            debug=self.debug,
            driver=self.driver,
            client=self.client,
            wallet=self.wallet,
            hlc_clock=self.hlc_clock,
            processing_delay=lambda: self.processing_delay_secs,
            executor=self.executor,
            get_last_processed_hlc=self.get_last_processed_hlc,
            get_last_hlc_in_consensus=self.get_last_hlc_in_consensus,
            stop_node=self.stop,
            reward_manager=self.reward_manager,
            reprocess=self.reprocess,
            check_if_already_has_consensus=self.check_if_already_has_consensus,
            stop_all_queues=self.stop_all_queues,
            start_all_queues=self.start_all_queues
        )

        self.validation_queue = validation_queue.ValidationQueue(
            testing=self.testing,
            driver=self.driver,
            debug=self.debug,
            consensus_percent=lambda: self.consensus_percent,
            get_peers_for_consensus=self.get_peers_for_consensus,
            process_from_consensus_result=self.process_from_consensus_result,
            hard_apply_block=self.hard_apply_block,
            set_peers_not_in_consensus=self.set_peers_not_in_consensus,
            wallet=self.wallet,
            stop_node=self.stop,
            stop_all_queues=self.stop_all_queues,
            start_all_queues=self.start_all_queues
        )

        self.total_processed = 0
        # how long to hold items in queue before processing

        self.work_validator = work.WorkValidator(
            wallet=wallet,
            main_processing_queue=self.main_processing_queue,
            hlc_clock=self.hlc_clock,
            get_masters=self.get_masternode_peers,
            get_last_processed_hlc=self.get_last_processed_hlc,
            stop_node=self.stop
        )

        self.block_contender = block_contender.Block_Contender(
            testing=self.testing,
            debug=self.debug,
            validation_queue=self.validation_queue,
            get_all_peers=self.get_all_peers,
            get_block_by_hlc=self.get_block_by_hlc,
            check_peer_in_consensus=self.check_peer_in_consensus,
            peer_add_strike=self.peer_add_strike,
            wallet=self.wallet,
            get_last_hlc_in_consensus=lambda: self.validation_queue.last_hlc_in_consensus
        )

        self.network.add_service(WORK_SERVICE, self.work_validator)
        self.network.add_service(CONTENDER_SERVICE, self.block_contender)

        self.running = False
        self.upgrade = False

        self.bypass_catchup = bypass_catchup

    async def start(self):
        # Start running
        self.running = True
        self.start_all_queues()

        if self.debug:
            asyncio.ensure_future(self.system_monitor.start(delay_sec=5))

        asyncio.ensure_future(self.check_main_processing_queue())
        asyncio.ensure_future(self.check_validation_queue())

        await self.network.start()

        for vk, ip in self.bootnodes.items():
            # print({"vk": vk, "ip": ip})
            if vk != self.wallet.verifying_key:
                # Use it to boot up the network
                socket = self.ctx.socket(zmq.SUB)
                self.network.connect(
                    socket=socket,
                    ip=ip,
                    key=vk,
                    wallet=self.wallet
                )

    def stop(self):
        # Kill the router and throw the running flag to stop the loop
        self.log.error("!!!!!! STOPPING NODE !!!!!!")
        self.network.stop()
        self.system_monitor.stop()
        self.running = False
        self.validation_queue.stop()
        self.main_processing_queue.stop
        tasks = asyncio.gather(
            self.main_processing_queue.stopping(),
            self.validation_queue.stopping()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)
        self.log.error("!!!!!! STOPPED NODE !!!!!!")

    def start_all_queues(self):
        self.main_processing_queue.start()
        self.validation_queue.start()

    async def stop_all_queues(self):
        self.main_processing_queue.stop()
        self.validation_queue.stop()

        await self.main_processing_queue.stopping()
        await self.validation_queue.stopping()

    async def stop_main_processing_queue(self):
        self.main_processing_queue.stop()
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
            await asyncio.sleep(0)

    async def check_main_processing_queue(self):
        while self.running:
            if len(self.main_processing_queue) > 0 and self.main_processing_queue.running:
                self.main_processing_queue.start_processing()

                try:
                    await self.process_main_queue()
                except Exception as err:
                    self.log.error(err)

                self.main_processing_queue.stop_processing()
            await asyncio.sleep(0)

    async def check_validation_queue(self):
        while self.running:
            if len(self.validation_queue) > 0 and self.validation_queue.running:
                self.validation_queue.start_processing()
                await self.validation_queue.process_next()
                self.log.info(f"Done processsing next and node is running {self.validation_queue.running}")
                self.validation_queue.stop_processing()
            await asyncio.sleep(0)

    async def process_main_queue(self):
        try:
            processing_results = await self.main_processing_queue.process_next()
        except Exception as err:
            print(err)

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

    def store_solution_and_send_to_network(self, processing_results):

        self.send_solution_to_network(processing_results=processing_results)

        self.validation_queue.append(
            processing_results=processing_results
        )

    def send_solution_to_network(self, processing_results):
        asyncio.ensure_future(self.network.publisher.publish(topic=CONTENDER_SERVICE, msg=processing_results))

    def soft_apply_current_state(self, hlc_timestamp):
        self.driver.soft_apply(hcl=hlc_timestamp)
        self.nonces.flush_pending()
        gc.collect()

    # Called by validation queue
    def process_from_consensus_result(self, hlc_timestamp):
        if self.testing:
            self.debug_timeline.append({
                'method': "process_from_consensus_result",
                'hlc_timestamp': hlc_timestamp,
                'last_processed': self.get_last_processed_hlc(),
                'last_consensus': self.get_last_hlc_in_consensus()
            })

        if self.debug:
            self.log.debug(json.dumps({
                'type': 'tx_lifecycle',
                'file': 'base',
                'event': 'process_from_consensus_result',
                'hlc_timestamp': hlc_timestamp,
                'last_processed': self.get_last_processed_hlc(),
                'last_consensus': self.get_last_hlc_in_consensus()
            }))

        processing_results = self.validation_queue.get_consensus_results(hlc_timestamp=hlc_timestamp)
        tx_result = processing_results.get('tx_result')
        state_changes = tx_result['state']
        stamps_used = tx_result['stamps_used']

        for s in state_changes:
            if type(s['value']) is dict:
                s['value'] = convert_dict(s['value'])

            self.driver.set(s['key'], s['value'])

        # self.driver.pending_reads.clear()
        # self.driver.pending_writes.clear()

        self.main_processing_queue.distribute_rewards(
            total_stamps_to_split=stamps_used,
            contract_name=tx_result['transaction']['payload']['contract']
        )

    def process_block(self, block_info, hlc_timestamp):
        # 2) Store block, create rewards and increment block number
        self.update_block_db(block_info)

        # 3) Soft Apply current state and create change log
        self.soft_apply_current_state(hlc_timestamp=hlc_timestamp)

        if self.testing:
            self.debug_processed_hlcs.append(hlc_timestamp)
            try:
                self.debug_stack.append({
                    'system_time': time.time(),
                    'method': 'process_result_after' + hlc_timestamp,
                    'pending_deltas': json.loads(encode(self.driver.pending_deltas).encode()),
                    'pending_writes': json.loads(encode(self.driver.pending_writes).encode()),
                    'pending_reads': json.loads(encode(self.driver.pending_reads).encode()),
                    'cache': json.loads(encode(self.driver.cache).encode()),
                    'block': self.get_current_height(),
                    'processing_results': hlc_timestamp,
                    'last_processed_hlc:': self.last_processed_hlc
                })
            except Exception as err:
                pass
                # print(err)
        '''
        if self.debug:
            self.log.debug(json.dumps({
                'type': 'tx_lifecycle',
                'file': 'base',
                'event': 'processed_from_main_queue',
                'hlc_timestamp': hlc_timestamp,
                'my_solution': block_info['hash'],
                'system_time': time.time()
            }))
        '''



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

    def create_new_block_from_result(self, result):
        # if self.testing:
        #   self.debug_stack.append({'method': 'create_new_block_from_result', 'block': self.current_height})
        # self.log.debug(result)


        # Create results copy without signatures
        result_without_sigs = deepcopy(result)
        result_without_sigs.pop('signatures', None)
        encoded_sb = encode(result_without_sigs)

        # Create block hash
        block_hasher = hashlib.sha3_256()
        block_hasher.update(encoded_sb.encode())

        # TODO blah
        ''' Committing a block
            1) is there a newer block?
                a) no
                    - apply new block
                    - return
                b) yes
                    - get all newer blocks in order
                    - figure out what my block number is
                    - take the previous hash from the next block
                    - re do block chain nonsense for later blocks
                    - apply state changes from current to latest
        '''



        block = {
            'hash': hash(tx['resut_hash'] + blocknumber + previoushash),
            'hlc': result['hlc_timestamp'],
            'number': self.get_current_height() + 1,
            'previous': self.get_current_hash(),
            'tx': result
        }

        return block

        self.blocks.soft_store_block(result['transactions'][0]['hlc_timestamp'], block)

        block_info = json.loads(encode(block).encode())

        '''
        if self.debug:
            self.log.debug(json.dumps({
                'type': 'tx_lifecycle',
                'file': 'base',
                'event': 'new_block',
                'block_info': block_info,
                'hlc_timestamp': result['transactions'][0]['hlc_timestamp'],
                'system_time': time.time()
            }))
        '''
        '''
        if self.testing:
            self.debug_stack.append({
                'type': 'tx_lifecycle',
                'file': 'base',
                'event': 'new_block',
                'block_info': block_info,
                'hlc_timestamp': result['transactions'][0]['hlc_timestamp'],
                'system_time': time.time()
            })
        '''
        return block_info

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
                await self.stop_main_processing_queue()
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

            # Next we'll cycle through the later blocks and remove any keys from the new_block_writes list if they are
            # overwritten.  This is so when we reprocess we don't rerun a transaction that depended on a key we already
            # had the correct value for.
            for block in later_blocks:
                tx_result = block.get('processed')
                block_state_changes = tx_result.get('state')

                for state_change in block_state_changes:
                    state_key = state_change.get('key')
                    if state_key in new_block_writes:
                        new_block_writes.remove(state_key)

                # Apply the state changes for this block to the db
                self.apply_state_changes_from_block(block)

            # Re-save each block to the database
            for block in later_blocks:
                self.blocks.store_block(block)

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

            # Hard apply this hlc_timestamps state changes
            if hlc_timestamp in self.driver.pending_deltas:
                self.driver.hard_apply(hlc_timestamp)
            else:
                self.apply_state_changes_from_block(new_block)

            # Store the block in the block db
            self.blocks.store_block(new_block)

            # Set the current block hash and height
            self.update_block_db(block=new_block)

        # remove the processing results and read history from the main_processing queue memory
        self.main_processing_queue.prune_history(hlc_timestamp=hlc_timestamp)

        # Increment the internal block counter
        self.current_block_height += 1

        '''
        # print({"hard_apply": hlc_timestamp})
        if self.debug:
            self.log.debug(json.dumps({
                'hlc_timestamp': hlc_timestamp,
                'consensus_hash': self.get_consensus_hash(),
                'current_hash': self.get_current_hash(),
                'event': 'commit_new_block',
                'type': 'tx_lifecycle',
                'file': 'base',
                'system_time': time.time()
            }))
        '''

# Re-processing CODE
    async def reprocess(self, tx):
        # make a copy of all the values before reprocessing, so we can compare transactions that are rerun
        pending_delta_history = deepcopy(self.driver.pending_deltas)

        # Get HLC of tx that needs to be run
        new_tx_hlc_timestamp = tx.get("hlc_timestamp")

        # Get the read history of all transactions that were run
        changed_keys_list = []

        # Add the New HLC to the list of hlcs so we can process it in order
        pending_delta_items = list(self.driver.pending_deltas.keys())
        pending_delta_items.append(new_tx_hlc_timestamp)
        pending_delta_items.sort()

        # Check the read_history if all HLCs that were processed, in order of oldest to newest
        for index, read_history_hlc in enumerate(pending_delta_items):

            # if this is the transaction we have to rerun,
            if read_history_hlc == new_tx_hlc_timestamp:
                if self.testing:
                    self.debug_reprocessing_results[read_history_hlc] = {
                        'reprocess_type': 'run',
                        'sent_to_network': True
                    }
                # rollback to this point
                self.rollback_drivers(hlc_timestamp=new_tx_hlc_timestamp)

                # Process the transaction
                processing_results = self.main_processing_queue.process_tx(tx=tx)
                self.soft_apply_current_state(hlc_timestamp=new_tx_hlc_timestamp)
                changed_keys_list = list(deepcopy(self.driver.pending_deltas[new_tx_hlc_timestamp].get('writes')))
                self.store_solution_and_send_to_network(processing_results=processing_results)
                continue

            # if the hlc is less than the hlc we need to run then leave it alone, it won't need any changes
            if read_history_hlc < new_tx_hlc_timestamp:
                continue

            # If HLC is greater than rollback point check it for reprocessing
            if read_history_hlc > new_tx_hlc_timestamp:
                self.reprocess_hlc(
                    hlc_timestamp=read_history_hlc,
                    pending_deltas=pending_delta_history.get(read_history_hlc, {}),
                    changed_keys_list=changed_keys_list
                )

    def reprocess_after_earlier_block(self, new_keys_list):
        # make a copy of all the values before reprocessing, so we can compare transactions that are rerun
        pending_delta_history = deepcopy(self.driver.pending_deltas)

        # Get the read history of all transactions that were run
        changed_keys_list = new_keys_list

        # Get and sort the list of HLCs so we can process it in order
        pending_delta_items = list(self.driver.pending_deltas.keys())
        pending_delta_items.sort()

        # Check the read_history if all HLCs that were processed, in order of oldest to newest
        for index, read_history_hlc in enumerate(pending_delta_items):
            self.reprocess_hlc(
                hlc_timestamp=read_history_hlc,
                pending_deltas=pending_delta_history.get(read_history_hlc, {}),
                changed_keys_list=changed_keys_list
            )

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
            transaction = self.validation_queue.get_processed_transaction(hlc_timestamp)

            try:
                # Reprocess the transaction
                processing_results = self.main_processing_queue.process_tx(tx=transaction)

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
                    self.store_solution_and_send_to_network(processing_results=processing_results)

                if self.testing:
                    self.debug_reprocessing_results[hlc_timestamp] = {
                        'reprocess_type': reprocess_type,
                        'sent_to_network': re_send_to_network
                    }

            except Exception as err:
                print(err)
        else:
            if self.testing:
                self.debug_reprocessing_results[hlc_timestamp] = {
                    'reprocess_type': "no_match",
                    'sent_to_network': False
                }

            for pending_delta_key, pending_delta_value in pending_deltas.items():
                self.driver.pending_writes[pending_delta_key] = pending_delta_value[1]

        self.soft_apply_current_state(hlc_timestamp=hlc_timestamp)

# ROLLBACK CODE
    def rollback(self, consensus_hlc_timestamp=""):
        if len(self.driver.pending_deltas) == 0:
            return

        if self.testing:
            self.debug_stack.sort(key=lambda x: x['system_time'])
            print(f"{self.upgrade_manager.node_type} {self.socket_base} ROLLING BACK")

        rollback_info = self.add_rollback_info()

        if self.debug:
            self.log.info(f"ROLLING BACK")
            self.log.debug(json.dumps({
                'type': 'node_info',
                'file': 'base',
                'event': 'rollback',
                'rollback_info': rollback_info,
                'amount_of_rollbacks': len(self.rollbacks),
                'system_time': time.time()
            }))

        self.rollback_drivers()
        self.add_processed_transactions_back_into_main_queue(consensus_hlc_timestamp=consensus_hlc_timestamp)
        self.reset_last_hlc_processed()
        self.validation_queue.clear_my_solutions()

        if self.testing:
            self.validation_queue.detected_rollback = False
            self.main_processing_queue.detected_rollback = False

    def add_rollback_info(self):
        called_from = "unknown"
        if self.main_processing_queue.detected_rollback:
            called_from = "main_processing_queue"
        if self.validation_queue.detected_rollback:
            called_from = "validation_queue"

        rollback_info = {
            'system_time': time.time(),
            'last_processed_hlc': self.last_processed_hlc,
            'last_hlc_in_consensus': self.validation_queue.last_hlc_in_consensus,
            'called_from': called_from
        }

        self.rollbacks.append(rollback_info)

        return rollback_info

    def rollback_drivers(self, hlc_timestamp):
        # Roll back the current state to the point of the last block consensus
        self.log.debug(f"Block Height Before: {self.get_current_height()}")
        # print(f"Block Height Before: {self.current_height}")
        # print(f"Block Height Before: {self.current_height}")
        # self.log.debug(encode(self.driver.pending_deltas))

        # print({"pending_deltas_BEFORE": json.loads(encode(self.driver.pending_deltas))})

        self.driver.rollback(hlc=hlc_timestamp)

        # Reset node to the rolled back height and hash
        # self.current_height = storage.get_latest_block_height(self.driver)
        # self.current_hash = storage.get_latest_block_hash(self.driver)

        self.log.debug(f"Block Height After: {self.get_current_height()}")
        # print(f"Block Height After: {self.current_height}")
        # print(f"Block Height After: {self.current_height}")

        # print({"pending_deltas_AFTER": json.loads(encode(self.driver.pending_deltas))})

    def add_processed_transactions_back_into_main_queue(self, consensus_hlc_timestamp=""):
        # print({"validation_queue_items": self.validation_queue.validation_results.items()})
        tx_added_back = 0

        # Add transactions I already processed back into the main_processing queue
        for hlc_timestamp, value in self.validation_queue.validation_results.items():
            if hlc_timestamp > consensus_hlc_timestamp:
                try:
                    transaction_processed = self.validation_queue.validation_results[hlc_timestamp].get('transaction_processed')
                    if transaction_processed is not None:
                        tx_added_back = tx_added_back + 1
                        self.main_processing_queue.append(tx=transaction_processed)

                except KeyError as err:
                    self.log.error(err)
                    pass

    def reset_last_hlc_processed(self):
        self.last_processed_hlc = self.validation_queue.last_hlc_in_consensus

###

    def _get_member_peers(self, contract_name):
        ''' GET FROM DB INSTEAD
        members = self.client.get_var(
            contract=contract_name,
            variable='S',
            arguments=['members']
        )
        '''

        members = self.driver.driver.get(f'{contract_name}.S:members')

        member_peers = dict()

        for member in members:
            ip = self.network.peers.get(member)
            if ip is not None:
                member_peers[member] = ip

        return member_peers

    def get_block_by_hlc(self, hlc_timestamp):
        return self.blocks.get_block(v=hlc_timestamp)

    def get_delegate_peers(self, not_me=False):
        peers = self._get_member_peers('delegates')
        if not_me and self.wallet.verifying_key in peers:
            del peers[self.wallet.verifying_key]
        return peers

    def get_masternode_peers(self, not_me=False):
        peers = self._get_member_peers('masternodes')

        if not_me and self.wallet.verifying_key in peers:
            del peers[self.wallet.verifying_key]

        return peers

    def get_all_peers(self, not_me=False):
        return {
            ** self.get_delegate_peers(not_me),
            ** self.get_masternode_peers(not_me)
        }

    def get_peers_for_consensus(self):
        allPeers = {}
        peers_from_blockchain = self.get_all_peers(not_me=True)
        for key in peers_from_blockchain:
            if self.network.peers[key].currently_participating():
                allPeers[key] = peers_from_blockchain[key]

        return allPeers

    def check_peer_in_consensus(self, key):
        try:
            return self.network.peers[key].in_consensus
        except KeyError:
            self.log.error(f'Cannot check if {key[:8]} is in consensus because they are not a peer!')
        return False

    def set_peers_not_in_consensus(self, keys):
        for key in keys:
            try:
                self.network.peers[key].not_in_consensus()
                self.log.info(f'DROPPED {key[:8]} FROM CONSENSUS!')
            except KeyError:
                self.log.error(f'Cannot drop {key[:8]} from consensus because they are not a peer!')

    def peer_add_strike(self, key):
        self.network.peers[key].add_strike()

    def make_constitution(self):
        return {
            'masternodes': self.get_masternode_peers(),
            'delegates': self.get_delegate_peers()
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

    def get_current_height(self):
        return storage.get_latest_block_height(self.driver)

    def get_current_hash(self):
        return storage.get_latest_block_hash(self.driver)

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