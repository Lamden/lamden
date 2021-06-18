from lamden import storage, network, router, authentication, rewards, upgrade, contracts
from lamden.nodes import execution, work, filequeue, processing_queue, validation_queue
from lamden.nodes import block_contender, contender, system_usage
from lamden.nodes.hlc import HLC_Clock
from lamden.contracts import sync
from lamden.logger.base import get_logger
from lamden.crypto.canonical import merklize, block_from_subblocks
from lamden.crypto.wallet import Wallet, verify
from lamden.new_sockets import Network

from contracting.db.driver import ContractDriver, encode
from contracting.execution.executor import Executor
from contracting.client import ContractingClient

import time
import json
from copy import deepcopy
import hashlib
import uvloop
import gc
import zmq.asyncio
import asyncio
from lamden.logger.base import get_logger
import decimal
from pathlib import Path
import uuid
import shutil
import os
import pathlib

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

BLOCK_SERVICE = 'catchup'
NEW_BLOCK_SERVICE = 'new_blocks'
WORK_SERVICE = 'work'
CONTENDER_SERVICE = 'contenders'

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
                 driver=ContractDriver(), debug=True, seed=None, bypass_catchup=False, node_type=None,
                 genesis_path=contracts.__path__[0], reward_manager=rewards.RewardManager(), nonces=storage.NonceStorage(), parallelism=4):

        self.consensus_percent = 51
        self.processing_delay_secs = {
            'base': 0.75,
            'self': 0.75
        }
        # amount of consecutive out of consensus solutions we will tolerate from out of consensus nodes
        self.max_peer_strikes = 5
        self.rollbacks = []

        self.driver = driver
        self.nonces = nonces

        self.seed = seed

        self.blocks = blocks

        self.log = get_logger('Base')
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

        self.seed_genesis_contracts()

        # self.socket_authenticator = authentication.SocketAuthenticator(
        #     bootnodes=self.bootnodes, ctx=self.ctx, client=self.client
        # )

        self.upgrade_manager = upgrade.UpgradeManager(client=self.client, wallet=self.wallet, node_type=node_type)

        self.router = router.Router(
            socket_id=socket_base,
            ctx=self.ctx,
            wallet=wallet,
            secure=True
        )
        '''
        self.network = network.Network(
            wallet=wallet,
            ip_string=socket_base,
            ctx=self.ctx,
            router=self.router
        )
        '''

        # wallet: Wallet, ctx: zmq.Context, socket_id

        self.network = Network(
            wallet=wallet,
            socket_id=socket_base,
            max_peer_strikes=self.max_peer_strikes,
            ctx=self.ctx,
        )

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver)
        self.reward_manager = reward_manager

        self.new_block_processor = NewBlock(driver=self.driver)
        # self.router.add_service(NEW_BLOCK_SERVICE, self.new_block_processor)

        self.current_height = lambda: storage.get_latest_block_height(self.driver)
        self.current_hash = lambda: storage.get_latest_block_hash(self.driver)

        self.file_queue = filequeue.FileQueue()
        self.main_processing_queue = processing_queue.ProcessingQueue(
            driver=self.driver,
            client=self.client,
            wallet=self.wallet,
            hlc_clock=self.hlc_clock,
            processing_delay=self.processing_delay_secs,
            executor=self.executor,
            get_current_hash=self.current_hash,
            get_current_height=self.current_height,
            stop_node=self.stop,
            reward_manager=self.reward_manager
        )

        self.validation_queue = validation_queue.ValidationQueue(
            consensus_percent=self.consensus_percent,
            get_peers_for_consensus=self.get_peers_for_consensus,
            hard_apply_block=self.hard_apply_block,
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
            get_last_processed_hlc=lambda: self.last_processed_hlc,
            stop_node=self.stop
        )

        self.block_contender = block_contender.Block_Contender(
            validation_queue=self.validation_queue,
            get_all_peers=self.get_all_peers,
            check_peer_in_consensus=self.check_peer_in_consensus,
            peer_add_strike=self.peer_add_strike,
            wallet=self.wallet
        )

        self.network.add_service(WORK_SERVICE, self.work_validator)
        self.network.add_service(CONTENDER_SERVICE, self.block_contender)

        self.running = False
        self.upgrade = False

        self.bypass_catchup = bypass_catchup

    async def start(self):
        # Start running
        self.running = True

        asyncio.ensure_future(self.system_monitor.start(delay_sec=5))
        asyncio.ensure_future(self.check_main_processing_queue())
        asyncio.ensure_future(self.check_validation_queue())

        await self.network.start()

        for vk, domain in self.bootnodes.items():
            if vk != self.wallet.verifying_key:
                # Use it to boot up the network
                socket = self.ctx.socket(zmq.SUB)
                self.network.connect(
                    socket=socket,
                    domain=domain,
                    key=vk,
                    wallet=self.wallet
                )

    def stop(self):
        # Kill the router and throw the running flag to stop the loop
        self.log.error("!!!!!! STOPPING NODE !!!!!!")
        self.network.stop()
        self.system_monitor.stop()
        self.running = False


    async def check_tx_queue(self):
        while self.running:
            if len(self.file_queue) > 0:
                tx_from_file = self.file_queue.pop(0)
                # TODO sometimes the tx info taken off the filequeue is None, investigate
                if tx_from_file is not None:
                    tx_message = self.make_tx_message(tx=tx_from_file)

                    # send the tx to the rest of the network
                    asyncio.ensure_future(self.send_tx_to_network(tx=tx_message))

                    # add this tx the processing queue so we can process it
                    self.main_processing_queue.append(tx=tx_message)
            await asyncio.sleep(0)

    async def check_main_processing_queue(self):
        while self.running:
            if len(self.main_processing_queue) > 0 and self.main_processing_queue.running:
                self.main_processing_queue.currently_processing = True
                await self.process_main_queue()
                self.main_processing_queue.currently_processing = False
            await asyncio.sleep(0)

    async def check_validation_queue(self):
        while self.running:
            if len(self.validation_queue) > 0 and self.validation_queue.running:
                await self.validation_queue.process_next()
            await asyncio.sleep(0)

    async def process_main_queue(self):
        processing_results = await self.main_processing_queue.process_next()

        if processing_results:
            self.last_processed_hlc = processing_results['hlc_timestamp']

            # ___ Change DB and State ___
            # 1) Needs to create the new block with our result
            block_info = self.create_new_block_from_result(processing_results['result'])

            # 2) Store block, create rewards and increment block number
            self.update_block_db(block_info)

            # 3) Soft Apply current state and create change log
            self.soft_apply_current_state(hlc_timestamp=processing_results['hlc_timestamp'])

            # ___ Validate and Send Block info __
            # add the hlc_timestamp to the needs validation queue for processing consensus later
            self.validation_queue.append(
                block_info=block_info,
                hlc_timestamp=processing_results['hlc_timestamp'],
                transaction_processed=processing_results['transaction_processed']
            )

            # send my block result to the rest of the network to prove I'm in consensus
            asyncio.ensure_future(self.send_block_to_network(block_info=block_info))

    async def send_block_to_network(self, block_info):
        await  self.network.publisher.publish(topic=CONTENDER_SERVICE, msg=block_info)

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

    async def send_tx_to_network(self, tx):
        await self.network.publisher.publish(topic=WORK_SERVICE, msg=tx)

    def create_new_block_from_result(self, result):
        # self.log.debug(result)
        bc = contender.BlockContender(total_contacts=1, total_subblocks=1)
        bc.add_sbcs([result])
        subblocks = bc.get_current_best_block()

        block = block_from_subblocks(subblocks, self.current_hash(), self.current_height() + 1)
        block_info = json.loads(encode(block).encode())

        self.blocks.soft_store_block(result['transactions'][0]['hlc_timestamp'], block)

        self.log.debug(json.dumps({
            'type': 'tx_lifecycle',
            'file': 'base',
            'event': 'new_block',
            'block_info': block_info,
            'hlc_timestamp': result['transactions'][0]['hlc_timestamp'],
            'system_time': time.time()
        }))

        return block_info

    def update_block_db(self, block):
        # TODO Do we need to tdo this again? it was done in "soft_apply_current_state" which is run before this
        self.driver.clear_pending_state()

        # self.log.info('Storing new block.')
        # Commit the state changes and nonces to the database
        # self.log.debug(block)
        storage.update_state_with_block(
            block=block,
            driver=self.driver,
            nonces=self.nonces
        )

        # self.log.info('Updating metadata.')
        # self.current_height = storage.get_latest_block_height(self.driver)
        # self.current_hash = storage.get_latest_block_hash(self.driver)

        self.new_block_processor.clean(self.current_height())

    def soft_apply_current_state(self, hlc_timestamp):
        self.driver.soft_apply(hlc_timestamp, self.driver.pending_writes)

        self.log.debug(json.dumps({
            'type': 'tx_lifecycle',
            'file': 'base',
            'event': 'soft_apply_after',
            'pending_deltas': encode(self.driver.pending_deltas[hlc_timestamp]),
            'hlc_timestamp': hlc_timestamp,
            'system_time': time.time()
        }))

        self.driver.clear_pending_state()
        self.nonces.flush_pending()
        gc.collect()

    def hard_apply_block(self, hlc_timestamp):
        self.driver.hard_apply(hlc_timestamp)
        self.blocks.commit(hlc_timestamp)

        self.log.debug(json.dumps({
            'type': 'tx_lifecycle',
            'file': 'base',
            'event': 'commit_new_block',
            'hlc_timestamp': hlc_timestamp,
            'system_time': time.time()
        }))

    async def rollback(self):
        # Stop the processing queue and await it to be done processing its last item
        self.main_processing_queue.stop()
        self.log.info(f"Awaiting queue stop: queue is processing... {self.main_processing_queue.currently_processing}")
        await self.main_processing_queue.stopping()
        self.log.info(f"Queue should be stopped: queue is processing... {self.main_processing_queue.currently_processing}")


        rollback_info = {
            'system_time': time.time(),
            'last_processed_hlc': self.last_processed_hlc,
            'last_hlc_in_consensus': self.validation_queue.last_hlc_in_consensus
        }

        self.rollbacks.append(rollback_info)

        self.log.debug(json.dumps({
            'type': 'node_info',
            'file': 'base',
            'event': 'rollback',
            'rollback_info': rollback_info,
            'amount_of_rollbacks': len(self.rollbacks),
            'system_time': time.time()
        }))

        # Roll back the current state to the point of the last block consensus
        self.driver.rollback()

        # Add transactions I already processed back into the main_processing queue
        for hlc_timestamp, value in self.validation_queue.validation_results.items():
            self.log.debug(hlc_timestamp)
            self.log.debug(self.validation_queue.validation_results[hlc_timestamp].get('transaction_processed'))

            tx_added_back = 0
            transaction_processed = self.validation_queue.validation_results[hlc_timestamp].get('transaction_processed')

            if transaction_processed:
                tx_added_back = tx_added_back + 1
                # Add the tx info back into the main processing queue
                self.main_processing_queue.append(tx=transaction_processed)

                '''
                my_solution = stored_results['solutions'].get(self.wallet.verifying_key)
                if my_solution:
                    # remove my solution from the consensus results
                    del self.validation_queue.validation_results[hlc_timestamp]['solutions'][self.wallet.verifying_key]

                    # decrement the number of solutions
                    # this ensures I will check consensus again once my new solution is added back
                    self.validation_queue.validation_results[hlc_timestamp]['last_check_info']['num_of_solutions'] -= 1
                '''

        self.log.info(f'Added back {tx_added_back} transactions for processing')

        # Restart the processing and validation queues
        self.main_processing_queue.start()
        self.validation_queue.start()

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

    async def catchup(self, mn_seed, mn_vk):
        # Get the current latest block stored and the latest block of the network
        self.log.info('Running catchup.')
        current = self.current_height()
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
