from lamden import storage, network, router, authentication, rewards, upgrade
import hashlib
from lamden.nodes import execution, work
from lamden.nodes.masternode import contender
from lamden.nodes.hlc import HLC_Clock
from contracting.execution.executor import Executor
from lamden.crypto.wallet import Wallet
from lamden.contracts import sync
from contracting.db.driver import ContractDriver, encode
import lamden
import zmq.asyncio
import asyncio
import json
from contracting.client import ContractingClient
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
import gc
from lamden.logger.base import get_logger
import decimal
import time
import math

from lamden.crypto.canonical import merklize, block_from_subblocks


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
                 driver=ContractDriver(), debug=True, store=False, seed=None, bypass_catchup=False, node_type=None,
                 genesis_path=lamden.contracts.__path__[0], reward_manager=rewards.RewardManager(), nonces=storage.NonceStorage(), parallelism=4):

        self.consensus_percent = 51

        self.driver = driver
        self.nonces = nonces
        self.store = store


        self.seed = seed

        self.blocks = blocks

        self.log = get_logger('Base')
        self.log.propagate = debug
        self.socket_base = socket_base
        self.wallet = wallet
        self.ctx = ctx

        self.genesis_path = genesis_path

        self.client = ContractingClient(
            driver=self.driver,
            submission_filename=genesis_path + '/submission.s.py'
        )

        self.bootnodes = bootnodes
        self.constitution = constitution

        self.seed_genesis_contracts()

        self.socket_authenticator = authentication.SocketAuthenticator(
            bootnodes=self.bootnodes, ctx=self.ctx, client=self.client
        )

        self.upgrade_manager = upgrade.UpgradeManager(client=self.client, wallet=self.wallet, node_type=node_type)

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

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver)
        self.transaction_executor = execution.SerialExecutor(executor=self.executor)

        self.new_block_processor = NewBlock(driver=self.driver)
        self.router.add_service(NEW_BLOCK_SERVICE, self.new_block_processor)

        self.main_processing_queue = []
        self.needs_validation_queue = []
        self.validation_results = {}

        self.total_processed = 0
        # how long to hold items in queue before processing
        self.processing_delay = 3
        self.hlc_clock = HLC_Clock(processing_delay=self.processing_delay)

        self.work_validator = work.WorkValidator(
            client=self.client,
            nonces=self.nonces,
            wallet=wallet,
            add_to_main_processing_queue=self.add_to_main_processing_queue,
            hlc_clock=self.hlc_clock,
            get_masters=self.get_masternode_peers
        )

        self.router.add_service(WORK_SERVICE, self.work_validator)

        self.running = False
        self.upgrade = False

        self.reward_manager = reward_manager

        self.current_height = storage.get_latest_block_height(self.driver)
        self.current_hash = storage.get_latest_block_hash(self.driver)

        self.bypass_catchup = bypass_catchup

    async def start(self):
        asyncio.ensure_future(self.router.serve())

        self.aggregator = contender.Aggregator(
            validation_results=self.validation_results,
            driver=self.driver,
        )

        # Get the set of VKs we are looking for from the constitution argument
        vks = self.constitution['masternodes'] + self.constitution['delegates']

        for node in self.bootnodes.keys():
            self.socket_authenticator.add_verifying_key(node)

        self.socket_authenticator.configure()

        # Use it to boot up the network
        await self.network.start(bootnodes=self.bootnodes, vks=vks)

        if not self.bypass_catchup:
            masternode_ip = None
            masternode = None

            if self.seed is not None:
                for k, v in self.bootnodes.items():
                    self.log.info(k, v)
                    if v == self.seed:
                        masternode = k
                        masternode_ip = v
            else:
                masternode = self.constitution['masternodes'][0]
                masternode_ip = self.network.peers[masternode]

            self.log.info(f'Masternode Seed VK: {masternode}')

            # Use this IP to request any missed blocks
            await self.catchup(mn_seed=masternode_ip, mn_vk=masternode)

        # Refresh the sockets to accept new nodes
        self.socket_authenticator.refresh_governance_sockets()

        # Start running
        self.running = True

    async def hang(self):
        # Maybe Upgrade
        ## self.upgrade_manager.version_check(constitution=self.make_constitution())

        # Hangs until upgrade is done

        '''
        while self.upgrade_manager.upgrade:
            await asyncio.sleep(0)
        '''

        # Wait for activity on our main processing queue or the needs validation queue
        while len(self.main_processing_queue) <= 0 and len(self.needs_validation_queue) <= 0:
            if not self.running:
                return

            await asyncio.sleep(0)

        # mn_logger.debug('Work available. Continuing.')

    async def loop(self):
        #await self.hang()
        if len(self.main_processing_queue) > 0:
            await self.process_main_queue()

        if len(self.needs_validation_queue) > 0:
            await self.process_needs_validation_queue()

        await asyncio.sleep(0)

    async def process_main_queue(self):
        # run top of stack if it's older than 1 second
        ## self.log.debug('{} waiting items in main queue'.format(len(self.main_processing_queue)))

        self.main_processing_queue.sort(key=lambda x: x['hlc_timestamp'])
        time_in_queue =  self.hlc_clock.check_timestamp_age(timestamp=self.main_processing_queue[0]['hlc_timestamp'])
        time_in_queue_seconds = time_in_queue / 1000000000
        # self.log.debug("First Item in queue is {} seconds old with an HLC TIMESTAMP of {}".format(time_in_queue_seconds, self.hlc_clock.get_new_hlc_timestamp()))

        # If the next item in the queue is old enough to process it then go ahead
        if time_in_queue_seconds > self.processing_delay:
            # Pop it out of the main processing queue
            tx = self.main_processing_queue.pop(0)

            # Process it to get the results
            results = self.process_tx(tx)

            # Store data about the tx so it can be processed for consensus later.
            self.validation_results[tx['hlc_timestamp']] = {}
            self.validation_results[tx['hlc_timestamp']]['delegate_solutions'] = {}
            self.validation_results[tx['hlc_timestamp']]['data'] = tx

            # add the hlc_timestamp to the needs validation queue for processing later
            self.add_to_needs_validation_queue(tx['hlc_timestamp'])

            # TODO This currently just udpates DB State but it should be cache
            # self.update_cache_state(results[0])

            # Mint new block
            block = block_from_subblocks(results, self.current_hash, self.current_height + 1)
            self.process_new_block(block)

            await self.send_block_results(results)

        # for x in range(len(self.main_processing_queue)):
        #    self.log.info(self.main_processing_queue[x]['hlc_timestamp'])

        await asyncio.sleep(0)

    async def process_needs_validation_queue(self):
        self.needs_validation_queue.sort()

        transaction_info = self.validation_results[self.needs_validation_queue[0]]

        consensus_info = self.check_consensus(transaction_info)

        self.log.debug(consensus_info)
        self.log.debug(transaction_info)

        if consensus_info['has_consensus']:
            self.log.info(f'{transaction_info["hlc_timestamp"]} HAS CONSENSUS')

            # remove the hlc_timestamp from the needs validation queue to prevent reprocessing
            self.needs_validation_queue.pop(0)

            if consensus_info['matches_me']:
                self.log.debug('I AM IN THE CONSENSUS')
            else:
                # TODO What to do if the node wasn't in the consensus group?

                # Get the actual solution result
                for delegate in transaction_info['delegate_solutions']:
                    if transaction_info['delegate_solutions'][delegate]['merkle_tree']['leaves'] == consensus_info['solution']:
                        results = transaction_info['delegate_solutions'][delegate]
                        # TODO Do something with the actual consensus solution
                        break


    def check_consensus(self, results):
        # Get the number of current delegates
        num_of_delegate = len(self.get_delegate_peers())

        # TODO How to set consensus percentage?
        # Cal the number of current delagates that need to agree
        consensus_needed = math.ceil(num_of_delegate * (self.consensus_percent / 100))

        # Get the current solutions
        delegate_solutions = results['delegate_solutions']
        total_solutions = len(delegate_solutions)

        # Return if we don't have enough responses to attempt a consensus check
        if (total_solutions < consensus_needed):
            return {
                'has_consensus': False,
                'consensus_needed': consensus_needed,
                'total_solutions': total_solutions
            }

        solutions = {}
        for delegate in delegate_solutions:
            solution = delegate_solutions[delegate]['merkle_tree']['leaves']

            if solution not in solutions:
                solutions[solution] = 1
            else:
                solutions[solution] += 1
            total_solutions += 1

        for solution in solutions:
            # if one solution has enough matches to put it over the consensus_needed
            # then we have consensus for this solution
            if solutions[solution] > consensus_needed:
                my_solution = delegate_solutions[self.wallet.verifying_key]['merkle_tree']['leaves']
                return {
                    'has_consensus': True,
                    'consensus_needed': consensus_needed,
                    'solution': solution,
                    'matches_me': my_solution == solution,
                    'total_solutions': total_solutions
                }

        # If we get here then there was either not enough responses to get consensus or we had a split
        # TODO what if split consensus? Probably very unlikely with a bunch of delegates but could happen
        return {
            'has_consensus': False,
            'consensus_needed': consensus_needed,
            'total_solutions': total_solutions
        }

    def process_tx(self, tx):
        ## self.log.debug("PROCESSING: {}".format(tx['input_hash']))

        # Run mini catch up here to prevent 'desyncing'
        # self.log.info(f'{len(self.new_block_processor.q)} new block(s) to process before execution.')

        results = self.transaction_executor.execute_work(
            driver=self.driver,
            work=[tx],
            wallet=self.wallet,
            previous_block_hash=self.current_hash,
            current_height=self.current_height,
            stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value'])
        )

        # self.log.debug(self.upgrade_manager.node_type)

        self.total_processed = self.total_processed + 1
        self.log.info('{} Processed: {} {}'.format(self.total_processed, tx['hlc_timestamp'], tx['tx']['metadata']['signature'][:12]))

        # self.new_block_processor.clean(self.current_height)
        # self.driver.clear_pending_state()

        return results

    async def send_block_results(self, results):
        await router.secure_multicast(
            msg=results,
            service=CONTENDER_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_all_peers(),
            ctx=self.ctx
        )

    async def add_from_webserver(self, tx):
        signed_transaction = self.make_tx(tx)
        #self.log.info("Adding {}")
        await self.send_work(signed_transaction)
        #await self.add_to_queue(signed_transaction)
        #self.log.info("Added transaction")

    def add_to_main_processing_queue(self, item):
        self.main_processing_queue.append(item)

    def add_to_needs_validation_queue(self, item):
        self.needs_validation_queue.append(item)


    def make_tx(self, tx):
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

    async def send_work(self, work):
        # Else, batch some more txs
        ## self.log.info('Sending transaction to other nodes.')

        # LOOK AT SOCKETS CLASS
        if len(self.get_delegate_peers()) == 0:
            self.log.error('No one online!')
            return False
        self.log.info(f'Sending work {work["hlc_timestamp"]} {work["tx"]["metadata"]["signature"][:12]}')
        await router.secure_multicast(
            msg=work,
            service=WORK_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_all_peers(),
            ctx=self.ctx
        )

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


    def process_new_block(self, block):
        # Update the state and refresh the sockets so new nodes can join
        self.update_database_state(block)

        self.socket_authenticator.refresh_governance_sockets()

        # Store the block if it's a masternode
        if self.store:
            encoded_block = encode(block)
            encoded_block = json.loads(encoded_block, parse_int=decimal.Decimal)

            self.blocks.store_block(encoded_block)

        # Prepare for the next block by flushing out driver and notification state
        # self.new_block_processor.clean()

        # Finally, check and initiate an upgrade if one needs to be done
        self.driver.commit()
        self.driver.clear_pending_state()
        gc.collect() # Force memory cleanup every block
        #self.nonces.flush_pending()


    def stop(self):
        # Kill the router and throw the running flag to stop the loop
        self.router.stop()
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

    def get_delegate_peers(self):
        peers = self._get_member_peers('delegates')
        # if self.wallet.verifying_key in peers:
        #     del peers[self.wallet.verifying_key]
        return peers

    def get_masternode_peers(self):
        peers = self._get_member_peers('masternodes')
        # if self.wallet.verifying_key in peers:
        #     del peers[self.wallet.verifying_key]
        return peers


    def get_all_peers(self):
        return {
            ** self.get_delegate_peers(),
            ** self.get_masternode_peers()
        }

    def make_constitution(self):
        return {
            'masternodes': self.get_masternode_peers(),
            'delegates': self.get_delegate_peers()
        }

