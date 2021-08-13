import asyncio
import gc
import hashlib
import json
import time

import uvloop
import zmq.asyncio
from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, encode
from contracting.db.encoder import convert_dict
from contracting.execution.executor import Executor
from lamden import storage, router, rewards, upgrade, contracts
from lamden.contracts import sync
from lamden.crypto.canonical import block_from_subblocks
from lamden.crypto.wallet import Wallet
from lamden.logger.base import get_logger
from lamden.new_sockets import Network
from lamden.nodes import block_contender, contender, system_usage
from lamden.nodes import work, processing_queue, validation_queue
from lamden.nodes.filequeue import FileQueue
from lamden.nodes.hlc import HLC_Clock

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

        self.log = get_logger('Base')
        self.debug = debug
        self.testing = testing
        self.debug_stack = []
        self.debug_processed_hlcs = []
        self.debug_processsing_results = []
        self.debug_blocks_processed = []
        self.debug_timeline = []

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
            get_current_hash=self.get_current_hash,
            get_current_height=self.get_current_height,
            get_last_processed_hlc=self.get_last_processed_hlc,
            get_last_hlc_in_consensus=self.get_last_hlc_in_consensus,
            stop_node=self.stop,
            reward_manager=self.reward_manager,
            rollback=self.rollback,
            check_if_already_has_consensus=self.check_if_already_has_consensus
        )

        self.validation_queue = validation_queue.ValidationQueue(
            testing=self.testing,
            debug=self.debug,
            consensus_percent=lambda: self.consensus_percent,
            get_peers_for_consensus=self.get_peers_for_consensus,
            process_from_consensus_result=self.process_from_consensus_result,
            hard_apply_block=self.hard_apply_block,
            is_next_block=self.is_next_block,
            set_peers_not_in_consensus=self.set_peers_not_in_consensus,
            rollback=self.rollback,
            wallet=self.wallet,
            stop_node=self.stop
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
            validation_queue=self.validation_queue,
            get_all_peers=self.get_all_peers,
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

        self.main_processing_queue.start()
        self.validation_queue.start()

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
                await self.process_main_queue()
                self.main_processing_queue.stop_processing()
            await asyncio.sleep(0)

    async def check_validation_queue(self):
        while self.running:
            if len(self.validation_queue) > 0 and self.validation_queue.running:
                self.validation_queue.start_processing()
                await self.validation_queue.process_next()
                self.validation_queue.stop_processing()
            await asyncio.sleep(0)

    async def process_main_queue(self):
        processing_results = await self.main_processing_queue.process_next()

        if processing_results:
            if self.testing:
                self.debug_processsing_results.append(processing_results)

            self.process_and_send_results(processing_results=processing_results)

    def process_and_send_results(self, processing_results):
        hlc_timestamp = processing_results['hlc_timestamp']

        # Return if the validation queue already processed this block
        if hlc_timestamp <= self.get_last_hlc_in_consensus():
            return

        if self.testing:
            self.debug_timeline.append({
                'method': "process_and_send_results",
                'hlc_timestamp': hlc_timestamp,
                'last_processed': self.get_last_processed_hlc(),
                'last_consensus': self.get_last_hlc_in_consensus()
            })

        block_info = self.process_result(processing_results=processing_results)
        self.process_block(block_info=block_info, hlc_timestamp=hlc_timestamp)
        self.send_solution_to_network(block_info=block_info, processing_results=processing_results)

    # Called by validation queue
    def process_from_consensus_result(self, block_info, hlc_timestamp):
        if self.testing:
            self.debug_timeline.append({
                'method': "process_from_consensus_result",
                'hlc_timestamp': hlc_timestamp,
                'last_processed': self.get_last_processed_hlc(),
                'last_consensus': self.get_last_hlc_in_consensus()
            })
        try:
            transaction = block_info['subblocks'][0]['transactions'][0]
            state_changes = transaction['state']
            stamps_used = transaction['stamps_used']

            for s in state_changes:
                if type(s['value']) is dict:
                    s['value'] = convert_dict(s['value'])

                self.driver.set(s['key'], s['value'])

            self.main_processing_queue.distribute_rewards(
                total_stamps_to_split=stamps_used,
                contract_name=transaction['payload']['contract']
            )

            self.process_block(block_info=block_info, hlc_timestamp=hlc_timestamp)
        except Exception as err:
            print(err)

    def process_result(self, processing_results):
        if self.testing:
            try:
                self.debug_stack.append({
                    'system_time': time.time(),
                    'method': 'process_result_before ' + processing_results["hlc_timestamp"],
                    'pending_deltas': json.loads(encode(self.driver.pending_deltas).encode()),
                    'pending_writes': json.loads(encode(self.driver.pending_writes).encode()),
                    'pending_reads': json.loads(encode(self.driver.pending_reads).encode()),
                    'cache': json.loads(encode(self.driver.cache).encode()),
                    'block': self.get.current_height(),
                    'consensus_block': self.get_consensus_height(),
                    'processing_results': processing_results,
                    'last_processed_hlc:': self.last_processed_hlc
                })
            except Exception as err:
                pass
                # print(err)

        # print({"processing_results":processing_results})
        self.last_processed_hlc = processing_results['hlc_timestamp']

        # ___ Change DB and State ___
        # 1) Needs to create the new block with our result
        block_info = self.create_new_block_from_result(processing_results['result'])


        return block_info

    def process_block(self, block_info, hlc_timestamp):
        # 2) Store block, create rewards and increment block number
        self.update_block_db(block_info)

        # 3) Soft Apply current state and create change log
        self.soft_apply_current_state(hlc_timestamp=hlc_timestamp)

        if self.testing:
            self.debug_processed_hlcs.append(hlc_timestamp)
            self.debug_blocks_processed.append(block_info)

        if self.testing:
            try:
                self.debug_stack.append({
                    'system_time': time.time(),
                    'method': 'process_result_after' + hlc_timestamp,
                    'pending_deltas': json.loads(encode(self.driver.pending_deltas).encode()),
                    'pending_writes': json.loads(encode(self.driver.pending_writes).encode()),
                    'pending_reads': json.loads(encode(self.driver.pending_reads).encode()),
                    'cache': json.loads(encode(self.driver.cache).encode()),
                    'block': self.get_current_height(),
                    'consensus_block': self.get_consensus_height(),
                    'processing_results': hlc_timestamp,
                    'last_processed_hlc:': self.last_processed_hlc
                })
            except Exception as err:
                pass
                # print(err)

        if self.debug:
            self.log.debug(json.dumps({
                'type': 'tx_lifecycle',
                'file': 'base',
                'event': 'processed_from_main_queue',
                'hlc_timestamp': hlc_timestamp,
                'my_solution': block_info['hash'],
                'system_time': time.time()
            }))

    def send_solution_to_network(self, block_info, processing_results):
        # ___ Validate and Send Block info __
        # add the hlc_timestamp to the needs validation queue for processing consensus later

        self.validation_queue.append(
            block_info=block_info,
            node_vk=self.wallet.verifying_key,
            hlc_timestamp=processing_results['hlc_timestamp'],
            transaction_processed=processing_results['transaction_processed']
        )
        asyncio.ensure_future(self.network.publisher.publish(topic=CONTENDER_SERVICE, msg=block_info))

    def make_tx_message(self, tx):
        timestamp = int(time.time())

        h = hashlib.sha3_256()
        h.update('{}'.format(timestamp).encode())
        input_hash = h.hexdigest()

        signature = self.wallet.sign(input_hash)

        return {
            'tx': tx,
            'timestamp': timestamp,
            'hlc_timestamp': self.hlc_clock.get_new_hlc_timestamp(),
            'signature': signature,
            'sender': self.wallet.verifying_key,
            'input_hash': input_hash
        }

    def create_new_block_from_result(self, result):
        # if self.testing:
        #   self.debug_stack.append({'method': 'create_new_block_from_result', 'block': self.current_height, 'consensus_block': self.get_consensus_height()})
        # self.log.debug(result)
        bc = contender.BlockContender(total_contacts=1, total_subblocks=1)
        bc.add_sbcs([result])
        subblocks = bc.get_current_best_block()

        # self.log.info(f'Current Height: {self.current_height}')

        block = block_from_subblocks(subblocks, self.get_current_hash(), self.get_current_height() + 1)

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
        #    self.debug_stack.append({'method': 'update_block_db', 'block': self.current_height, 'consensus_block': self.get_consensus_height()})
        # TODO Do we need to tdo this again? it was done in "soft_apply_current_state" which is run before this
        # self.driver.clear_pending_state()

        # Commit the state changes and nonces to the database

        storage.set_latest_block_hash(block['hash'], driver=self.driver)
        storage.set_latest_block_height(block['number'], driver=self.driver)

        self.new_block_processor.clean(self.get_current_height())

    def soft_apply_current_state(self, hlc_timestamp):
        '''
        if self.testing:
            self.debug_stack.append({'system_time' :time.time(), 'method': 'soft_apply_current_state_before', 'block': self.current_height, 'consensus_block': self.get_consensus_height()})
        '''
        self.driver.soft_apply(hlc_timestamp)
        '''
        if self.testing:
            self.debug_stack.append({'system_time' :time.time(), 'method': 'soft_apply_current_state_after', 'block': self.current_height,
                                 'consensus_block': self.get_consensus_height()})
        '''
        # print({"soft_apply": hlc_timestamp})
        ''' Can't do this event 
        self.log.debug(json.dumps({
            'type': 'tx_lifecycle',
            'file': 'base',
            'event': 'soft_apply_after',
            'pending_deltas': encode(self.driver.pending_deltas[hlc_timestamp]),
            'hlc_timestamp': hlc_timestamp,
            'system_time': time.time()
        }))
        '''


        # Commented out because Stu told me too
        # self.driver.clear_pending_state()

        self.nonces.flush_pending()
        gc.collect()

    def hard_apply_block(self, hlc_timestamp):
        if self.testing:
            self.debug_stack.append({'system_time' :time.time(), 'method': 'hard_apply_block', 'consensus_block': self.get_consensus_height(), 'hlc_timestamp': hlc_timestamp})

        # state changes hard apply
        self.driver.hard_apply(hlc_timestamp)
        # block data hard apply
        self.blocks.commit(hlc_timestamp)

        # print({"hard_apply": hlc_timestamp})
        if self.debug:
            self.log.debug(json.dumps({
                'type': 'tx_lifecycle',
                'file': 'base',
                'event': 'commit_new_block',
                'hlc_timestamp': hlc_timestamp,
                'system_time': time.time()
            }))

### ROLLBACK CODE
    async def rollback(self):
        if self.testing:
            self.debug_stack.sort(key=lambda x: x['system_time'])
            print(f"{self.upgrade_manager.node_type} {self.socket_base} ROLLING BACK")

        # Stop the processing queue and await it to be done processing its last item
        self.main_processing_queue.stop()
        self.validation_queue.stop()

        await self.main_processing_queue.stopping()
        await self.validation_queue.stopping()

        rollback_info = self.add_rollback_info()
        if self.debug:
            self.log.debug(json.dumps({
                'type': 'node_info',
                'file': 'base',
                'event': 'rollback',
                'rollback_info': rollback_info,
                'amount_of_rollbacks': len(self.rollbacks),
                'system_time': time.time()
            }))

        # sleep 2 seconds to see if a previous HLC tx comes in
        asyncio.sleep(2)

        self.rollback_drivers()
        self.add_processed_transactions_back_into_main_queue()
        self.reset_last_hlc_processed()
        self.validation_queue.clear_my_solutions()

        if self.testing:
            self.validation_queue.detected_rollback = False
            self.main_processing_queue.detected_rollback = False

        # Restart the processing and validation queues
        self.main_processing_queue.start()
        self.validation_queue.start()

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

    def rollback_drivers(self):
        # Roll back the current state to the point of the last block consensus
        self.log.debug(f"Block Height Before: {self.get_current_height()}")
        # print(f"Block Height Before: {self.current_height}")
        # print(f"Block Height Before: {self.current_height}")
        # self.log.debug(encode(self.driver.pending_deltas))

        # print({"pending_deltas_BEFORE": json.loads(encode(self.driver.pending_deltas))})

        self.driver.rollback()

        # Reset node to the rolled back height and hash
        # self.current_height = storage.get_latest_block_height(self.driver)
        # self.current_hash = storage.get_latest_block_hash(self.driver)

        self.log.debug(f"Block Height After: {self.get_current_height()}")
        # print(f"Block Height After: {self.current_height}")
        # print(f"Block Height After: {self.current_height}")

        # print({"pending_deltas_AFTER": json.loads(encode(self.driver.pending_deltas))})

    def add_processed_transactions_back_into_main_queue(self):
        # print({"validation_queue_items": self.validation_queue.validation_results.items()})
        tx_added_back = 0

        # Add transactions I already processed back into the main_processing queue
        for hlc_timestamp, value in self.validation_queue.validation_results.items():
            try:

                transaction_processed = self.validation_queue.validation_results[hlc_timestamp].get('transaction_processed')
                if transaction_processed is not None:
                    tx_added_back = tx_added_back + 1
                    self.main_processing_queue.append(tx=transaction_processed)

            except KeyError as err:
                self.log.error(err)
                pass

    def reset_last_hlc_processed(self):
        self.main_processing_queue.sort_queue()
        self.last_processed_hlc = self.validation_queue.last_hlc_in_consensus

###

    def _get_member_peers(self, contract_name):
        members = self.client.get_var(
            contract=contract_name,
            variable='S',
            arguments=['members']
        )

        member_peers = dict()

        for member in members:
            ip = self.network.peers.get(member)
            if ip is not None:
                member_peers[member] = ip

        return member_peers

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

    def get_consensus_height(self):
        return self.driver.driver.get(DB_CURRENT_BLOCK_HEIGHT)

    def get_consensus_hash(self):
        hash =  self.driver.driver.get(DB_CURRENT_BLOCK_HASH)
        if hash is None:
            return 64 * f'0'
        return hash

    def get_current_height(self):
        return storage.get_latest_block_height(self.driver)

    def get_current_hash(self):
        return storage.get_latest_block_hash(self.driver)

    def get_last_processed_hlc(self):
        return self.last_processed_hlc

    def get_last_hlc_in_consensus(self):
        return self.validation_queue.last_hlc_in_consensus

    def is_next_block(self, previous_hash):
        self.log.debug(
            {'current_hash': self.get_consensus_hash(),
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