from lamden import storage, network, router, authentication, rewards, upgrade
from lamden.nodes import base
import hashlib
from lamden.crypto import canonical
from lamden.nodes.delegate import execution, work
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
from collections import defaultdict
import time
from lamden.crypto.wallet import verify
from lamden.crypto import transaction
from hlcpy import HLC


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

class WorkProcessor(router.Processor):
    def __init__(self, client: ContractingClient, nonces: storage.NonceStorage, debug=True, expired_batch=5,
                 tx_timeout=5):

        self.main_processing_queue = []
        self.tx_expiry = 1001

        self.log = get_logger('Work Inbox')
        self.log.propagate = debug

        self.masters = []
        self.tx_timeout = tx_timeout

        self.client = client
        self.nonces = nonces

        self.hlc_clock = HLC()
        self.hlc_clock.sync()


    async def process_message(self, msg):
        self.log.info(f'Received work from {msg["sender"][:8]}')

        if msg['sender'] not in self.masters:
            self.log.error(f'TX Batch received from non-master {msg["sender"][:8]}')
            return

        if not verify(vk=msg['sender'], msg=msg['input_hash'], signature=msg['signature']):
            self.log.error(f'Invalidly signed TX Batch received from master {msg["sender"][:8]}')

        if await self.check_expired(msg['hlc_timestamp']):
            self.log.error(f'Expired TX from master {msg["sender"][:8]}')
            return

        transaction.transaction_is_valid(
            transaction=msg['tx'],
            expected_processor=msg['sender'],
            client=self.client,
            nonces=self.nonces,
            strict=False
        )

        self.merge_hlc_timestamp(msg['hlc_timestamp'])
        self.add_to_queue(msg)

        self.log.info(f'Received new work from {msg["sender"][:8]} to my queue.')

    async def add_from_webserver(self, tx):
        signed_transaction = self.make_tx(tx)

        self.send_work(signed_transaction)
        self.add_to_queue(signed_transaction)

    async def add_to_queue(self, item):
        self.main_processing_queue.append(item)
        self.main_processing_queue.sort(key=lambda x: x['hlc_timestamp'], reverse=True)

    async def get_new_hlc_timestamp(self):
        self.hlc_clock.sync()
        return str(self.hlc_clock())

    async def merge_hlc_timestamp(self, event_timestamp):
        self.hlc_clock.merge(event_timestamp)

    async def check_hlc_age(self, timestamp):
        # Convert timestamp to HLC clock then to nanoseconds
        temp_hlc = HLC()
        temp_hlc.from_str(timestamp)
        timestamp_nanoseconds, _ = temp_hlc.tuple()

        # sync out clock and then get its nanoseconds
        self.hlc_clock.sync()
        internal_nanoseconds, _ = self.hlc_clock.tuple()

        # Return the difference
        return internal_nanoseconds - timestamp_nanoseconds

    async def check_expired(self, timestamp):
        return await self.check_hlc_age(timestamp) >= self.tx_expiry

    async def make_tx(self, tx):
        timestamp = int(time.time())

        h = hashlib.sha3_256()
        h.update('{}'.format(timestamp).encode())
        input_hash = h.hexdigest()

        signature = self.wallet.sign(input_hash)

        return {
            'tx': tx,
            'timestamp': timestamp,
            'hlc_timestamp': await self.get_new_hlc_timestamp(),
            'signature': signature,
            'sender': self.wallet.verifying_key,
            'input_hash': input_hash
        }

    async def send_work(self, work):
        # Else, batch some more txs
        self.log.info('Sending transaction to other nodes.')

        # LOOK AT SOCKETS CLASS
        if len(self.get_delegate_peers()) == 0:
            self.log.error('No one online!')
            return False

        await router.secure_multicast(
            msg=work,
            service=base.WORK_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_all_peers(),
            ctx=self.ctx
        )

class Node:
    def __init__(self, socket_base, ctx: zmq.asyncio.Context, wallet, constitution: dict, bootnodes={}, blocks=storage.BlockStorage(),
                 driver=ContractDriver(), debug=True, store=False, seed=None, bypass_catchup=False, node_type=None,
                 genesis_path=lamden.contracts.__path__[0], reward_manager=rewards.RewardManager(), nonces=storage.NonceStorage(), parallelism=4):

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
        self.work_processor = WorkProcessor(client=self.client, nonces=self.nonces)
        self.router.add_service(WORK_SERVICE, self.work_processor)

        self.running = False
        self.upgrade = False

        self.reward_manager = reward_manager

        self.current_height = storage.get_latest_block_height(self.driver)
        self.current_hash = storage.get_latest_block_hash(self.driver)

        self.bypass_catchup = bypass_catchup

    async def hang(self):
        # Maybe Upgrade
        self.upgrade_manager.version_check(constitution=self.make_constitution())

        # Hangs until upgrade is done
        while self.upgrade_manager.upgrade:
            await asyncio.sleep(0)

        # Wait for activity on our transaction queue or new block processor.
        # If another masternode has transactions, it will send use a new block notification.
        # If we have transactions, we will do the opposite. This 'wakes' up the network.
        self.log.debug('Waiting for work work...')

        while len(self.work_processor.main_processing_queue) <= 0:
            if not self.running:
                return

            await asyncio.sleep(0)

        # mn_logger.debug('Work available. Continuing.')

    async def loop(self):
        await self.hang()
        await self.process_main_queue()

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
        self.log.info(f'Processing block #{block.get("number")}')
        # Test if block failed immediately
        if block == {'response': 'ok'}:
            return False

        if block['hash'] == 'f' * 64:
            self.log.error('Failed Block! Not storing.')
            return False

        # Get current metastate
        # if len(block['subblocks']) < 1:
        #    return False

        # Test if block contains the same metastate
        # if block['number'] != self.current_height + 1:
        #     self.log.info(f'Block #{block["number"]} != {self.current_height + 1}. '
        #                   f'Node has probably already processed this block. Continuing.')
        #     return False

        # if block['previous'] != self.current_hash:
        #     self.log.error('Previous block hash != Current hash. Cryptographically invalid. Not storing.')
        #     return False

        # If so, use metastate and subblocks to create the 'expected' block
        # expected_block = canonical.block_from_subblocks(
        #     subblocks=block['subblocks'],
        #     previous_hash=self.current_hash,
        #     block_num=self.current_height + 1
        # )

        # Return if the block contains the expected information
        # good = block == expected_block
        # if good:
        #     self.log.info(f'Block #{block["number"]} passed all checks. Store.')
        # else:
        #     self.log.error(f'Block #{block["number"]} has an encoding problem. Do not store.')
        #
        # return good

        return True

    def update_state(self, block):
        self.driver.clear_pending_state()

        # Check if the block is valid
        if self.should_process(block):
            self.log.info('Storing new block.')
            # Commit the state changes and nonces to the database
            storage.update_state_with_block(
                block=block,
                driver=self.driver,
                nonces=self.nonces
            )

            self.log.info('Issuing rewards.')
            # Calculate and issue the rewards for the governance nodes
            self.reward_manager.issue_rewards(
                block=block,
                client=self.client
            )

        self.log.info('Updating metadata.')
        self.current_height = storage.get_latest_block_height(self.driver)
        self.current_hash = storage.get_latest_block_hash(self.driver)

        self.new_block_processor.clean(self.current_height)

    def process_new_block(self, block):
        # Update the state and refresh the sockets so new nodes can join
        self.update_state(block)
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

    async def start(self):
        asyncio.ensure_future(self.router.serve())

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

    async def process_main_queue(self):
        # run all transactions older than 1 sec
        self.log.debug(len(self.work_processor.main_processing_queue), 'items in main queue')
        await asyncio.sleep(0)

    async def process_new_work(self):
        if len(self.get_masternode_peers()) == 0:
            return

        filtered_work = await self.acquire_work()

        # Run mini catch up here to prevent 'desyncing'
        self.log.info(f'{len(self.new_block_processor.q)} new block(s) to process before execution.')

        while len(self.new_block_processor.q) > 0:
            block = self.new_block_processor.q.pop(0)
            self.process_new_block(block)

        results = self.transaction_executor.execute_work(
            driver=self.driver,
            work=filtered_work,
            wallet=self.wallet,
            previous_block_hash=self.current_hash,
            current_height=self.current_height,
            stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value'])
        )

        await router.secure_multicast(
            msg=results,
            service=base.CONTENDER_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_masternode_peers(),
            ctx=self.ctx
        )

        self.log.info(f'Work execution complete. Sending to masters.')

        self.new_block_processor.clean(self.current_height)
        self.driver.clear_pending_state()

    async def acquire_work(self):
        current_masternodes = self.client.get_var(contract='masternodes', variable='S', arguments=['members'])

        w = await self.work_processor.gather_transaction_batches(masters=current_masternodes)

        self.log.info(f'Got {len(w)} batch(es) of work')

        expected_masters = set(current_masternodes)
        work.pad_work(work=w, expected_masters=list(expected_masters))

        return work.filter_work(w)

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
        return self._get_member_peers('delegates')

    def get_masternode_peers(self):
        return self._get_member_peers('masternodes')

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
