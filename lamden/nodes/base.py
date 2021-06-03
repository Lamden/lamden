from lamden import storage, network, router, authentication, rewards, upgrade, contracts
from lamden.nodes import execution, work, filequeue, processing_queue, validation_queue
from lamden.nodes import contender
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
        self.processing_delay_secs = 1.5

        self.driver = driver
        self.nonces = nonces

        self.seed = seed

        self.blocks = blocks

        self.log = get_logger('Base')
        self.log.propagate = debug
        self.socket_base = socket_base
        self.wallet = wallet
        self.hlc_clock = HLC_Clock(processing_delay=self.processing_delay_secs)
        self.ctx = ctx

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
            ctx=self.ctx,
        )

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver)
        self.transaction_executor = execution.SerialExecutor(executor=self.executor)

        self.new_block_processor = NewBlock(driver=self.driver)
        # self.router.add_service(NEW_BLOCK_SERVICE, self.new_block_processor)

        self.file_queue = filequeue.FileQueue()
        self.main_processing_queue = processing_queue.ProcessingQueue(
            driver=self.driver,
            client=self.client,
            wallet=self.wallet,
            hlc_clock=self.hlc_clock,
            processing_delay=self.processing_delay_secs,
            transaction_executor=self.transaction_executor,
            get_current_hash=lambda: self.current_hash,
            get_current_height=lambda: self.current_height
        )

        self.validation_queue = validation_queue.ValidationQueue(
            consensus_percent=self.consensus_percent,
            get_all_peers=self.get_all_peers,
            create_new_block=self.create_new_block,
            wallet=self.wallet,
            stop=self.stop
        )

        self.total_processed = 0
        # how long to hold items in queue before processing

        self.work_validator = work.WorkValidator(
            wallet=wallet,
            main_processing_queue=self.main_processing_queue,
            hlc_clock=self.hlc_clock,
            get_masters=self.get_masternode_peers
        )

        self.aggregator = contender.Aggregator(
            validation_queue=self.validation_queue,
            get_all_peers=self.get_all_peers,
            driver=self.driver,
            wallet=self.wallet
        )

        # self.router.add_service(WORK_SERVICE, self.work_validator)
        # self.router.add_service(CONTENDER_SERVICE, self.aggregator.sbc_inbox)
        self.network.add_service(WORK_SERVICE, self.work_validator)
        self.network.add_service(CONTENDER_SERVICE, self.aggregator.sbc_inbox)

        self.running = False
        self.upgrade = False

        self.reward_manager = reward_manager

        self.current_height = storage.get_latest_block_height(self.driver)
        self.current_hash = storage.get_latest_block_hash(self.driver)

        self.bypass_catchup = bypass_catchup

    async def start(self):
        # Start running
        self.running = True
        asyncio.ensure_future(self.check_tx_queue())
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

    async def check_tx_queue(self):
        while self.running:
            if len(self.file_queue) > 0:
                await self.send_tx_to_network(self.file_queue.pop(0))
            await asyncio.sleep(0)

    async def check_main_processing_queue(self):
        while self.running:
            if len(self.main_processing_queue) > 0:
                await self.process_main_queue()
            await asyncio.sleep(0)

    async def check_validation_queue(self):
        while self.running:
            if len(self.validation_queue) > 0:
                await self.validation_queue.process_next()
            await asyncio.sleep(0)

    async def process_main_queue(self):
        processing_results = self.main_processing_queue.process_next()

        if processing_results:
            # add the hlc_timestamp to the needs validation queue for processing later
            self.validation_queue.append(processing_results)

            # Mint new block
            self.create_new_block(deepcopy(processing_results['results']))
            await self.send_solution_to_network(results=deepcopy(processing_results['results']))

            # TODO This currently just udpates DB State but it should be cache
            # self.save_cached_state(results=results)

            # self.log.info("\n------ MY RESULTS -----------")
            # self.log.debug(processing_results)
            # self.log.info("\n-----------------------------")
            return True
        else:
            return False

    async def send_solution_to_network(self, results):
        asyncio.ensure_future(self.network.publisher.publish(topic=CONTENDER_SERVICE, msg=results))
        self.network.add_message_to_subscriptions_queue(topic=CONTENDER_SERVICE, msg=results)
        '''
        await router.secure_multicast(
            msg=results,
            service=CONTENDER_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_all_peers(not_me=True),
            ctx=self.ctx
        )
        '''

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
        tx_message = self.make_tx_message(tx)
        # self.log.debug(tx_message)
        # Else, batch some more txs
        ## self.log.info('Sending transaction to other nodes.')

        # LOOK AT SOCKETS CLASS
        if len(self.get_delegate_peers()) == 0:
            self.log.error('No one online!')
            return False

        await self.network.publisher.publish(topic=WORK_SERVICE, msg=tx_message)
        self.network.add_message_to_subscriptions_queue(topic=WORK_SERVICE, msg=tx_message)

        '''
            await router.secure_multicast(
                msg=tx_message,
                service=WORK_SERVICE,
                cert_dir=self.socket_authenticator.cert_dir,
                wallet=self.wallet,
                peer_map=self.get_all_peers(),
                ctx=self.ctx
            )
        '''

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

    def update_database_state(self, block):
        self.driver.clear_pending_state()

        # Check if the block is valid
        if self.should_process(block):
            # self.log.info('Storing new block.')
            # Commit the state changes and nonces to the database
            # self.log.debug(block)
            storage.update_state_with_block(
                block=block,
                driver=self.driver,
                nonces=self.nonces
            )

            # self.log.info('Issuing rewards.')
            # Calculate and issue the rewards for the governance nodes
            self.reward_manager.issue_rewards(
                block=block,
                client=self.client
            )

        # self.log.info('Updating metadata.')
        self.current_height = storage.get_latest_block_height(self.driver)
        self.current_hash = storage.get_latest_block_hash(self.driver)

        self.new_block_processor.clean(self.current_height)

    def update_cache_state(self, results):
        # TODO This should be the actual cache write but it's HDD for now
        self.driver.clear_pending_state()

        storage.update_state_with_transaction(
            tx=results['transactions'][0],
            driver=self.driver,
            nonces=self.nonces
        )

    def create_new_block(self, results):
        bc = contender.BlockContender(total_contacts=1, total_subblocks=1)
        bc.add_sbcs(results)
        subblocks = bc.get_current_best_block()

        if (len(subblocks) == 0):
            self.log.debug(subblocks)
            self.log.debug(results)
            self.log.error("---------------------------------------------------------------")
            self.log.error("--------------- NO SUB BLOCKS!!! ---------------")
            self.log.error("--------------------------------------------------------------------")

        block = block_from_subblocks(subblocks, self.current_hash, self.current_height + 1)
        self.process_new_block(block, results[0]['transactions'][0]['hlc_timestamp'])

    def process_new_block(self, block, hlc_timestamp):
        # TODO hlc_timestamp can be removed from args as it's only there for dev debugging

        # Update the state and refresh the sockets so new nodes can join
        # TODO re-enable when cached state is implemented
        # self.update_database_state(block)

        block_info = json.loads(encode(block).encode())

        self.log.debug(json.dumps({
            'type': 'tx_lifecycle',
            'file': 'base',
            'event': 'new_block',
            'block_info': block_info,
            'hlc_timestamp': hlc_timestamp,
            'system_time': time.time()
        }))

        self.blocks.store_block(block)
        self.save_cached_state(block_info)

    def save_cached_state(self, block):
        self.update_database_state(block)
        self.driver.commit()
        self.driver.clear_pending_state()
        self.nonces.flush_pending()
        gc.collect()

    def stop(self):
        # Kill the router and throw the running flag to stop the loop
        self.network.stop()
        self.running = False

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


    def make_constitution(self):
        return {
            'masternodes': self.get_masternode_peers(),
            'delegates': self.get_delegate_peers()
        }
