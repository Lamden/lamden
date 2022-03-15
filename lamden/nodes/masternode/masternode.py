import asyncio
import hashlib
import time
from lamden import router
from lamden.crypto.wallet import Wallet
from lamden.storage import BlockStorage, get_latest_block_height
from lamden.nodes.masternode import contender, webserver
from lamden.nodes.base import FileQueue
from lamden.formatting import primatives
from lamden.nodes import base
from contracting.db.driver import ContractDriver
from contracting.db.encoder import decode
import copy
from lamden.logger.base import get_logger

mn_logger = get_logger('Masternode')

BLOCK_SERVICE = 'service'


class BlockService(router.Processor):
    def __init__(self, blocks: BlockStorage=None, driver=ContractDriver()):
        self.blocks = blocks
        self.driver = driver

    async def process_message(self, msg):
        response = None
        mn_logger.debug('Got a msg')
        mn_logger.debug(msg)
        if primatives.dict_has_keys(msg, keys={'name', 'arg'}):
            if msg['name'] == base.GET_BLOCK:
                response = self.get_block(msg)
            elif msg['name'] == base.GET_HEIGHT:
                response = get_latest_block_height(self.driver)

        return response

    def get_block(self, command):
        num = command.get('arg')
        if not primatives.number_is_formatted(num):
            return None

        block = self.blocks.get_block(num)

        if block is None:
            return None

        return block


class TransactionBatcher:
    def __init__(self, wallet: Wallet, queue=FileQueue()):
        self.wallet = wallet
        self.queue = queue

    def make_batch(self, transactions):
        timestamp = int(time.time())

        h = hashlib.sha3_256()
        h.update('{}'.format(timestamp).encode())
        input_hash = h.hexdigest()

        signature = self.wallet.sign(input_hash)

        batch = {
            'transactions': [t for t in transactions],
            'timestamp': timestamp,
            'signature': signature,
            'sender': self.wallet.verifying_key,
            'input_hash': input_hash
        }

        mn_logger.debug(f'Made new batch of {len(transactions)} transactions.')

        return batch

    def pack_current_queue(self, tx_number=250):
        tx_list = []

        # len(tx_list) < tx_number and

        while len(self.queue) > 0:
            tx_list.append(self.queue.pop(0))

        batch = self.make_batch(tx_list)

        return batch


class Masternode(base.Node):
    def __init__(self, webserver_port=8080, *args, **kwargs):
        super().__init__(store=True, *args, **kwargs)
        # Services
        self.webserver_port = webserver_port
        self.webserver = webserver.WebServer(
            contracting_client=self.client,
            driver=self.driver,
            blocks=self.blocks,
            wallet=self.wallet,
            port=self.webserver_port
        )
        self.upgrade_manager.webserver_port = self.webserver_port
        self.upgrade_manager.node_type = 'masternode'

        self.tx_batcher = TransactionBatcher(wallet=self.wallet, queue=FileQueue())
        self.webserver.queue = self.tx_batcher.queue

        self.aggregator = contender.Aggregator(
            driver=self.driver,
        )

        self.router.add_service(base.CONTENDER_SERVICE, self.aggregator.sbc_inbox)

        # Network upgrade flag
        self.active_upgrade = False

    async def start(self):
        self.router.add_service(base.BLOCK_SERVICE, BlockService(self.blocks, self.driver))

        await super().start()

        members = self.driver.get_var(contract='masternodes', variable='S', arguments=['members'], mark=False)
        assert self.wallet.verifying_key in members, 'You are not a masternode!'

        # Start the block server so others can run catchup using our node as a seed.
        # Start the block contender service to participate in consensus
        # self.router.add_service(base.CONTENDER_SERVICE, self.aggregator.sbc_inbox)

        self.log.info('Done starting...')

        # If we have no blocks in our database, we are starting a new network from scratch

        asyncio.ensure_future(self.new_blockchain_boot())

        # if self.current_height == 0:
        #     asyncio.ensure_future(self.new_blockchain_boot())
        # # Otherwise, we are joining an existing network quorum
        # else:
        #     asyncio.ensure_future(self.join_quorum())
        self.log.debug('returned')

    async def hang(self):
        # Wait for activity on our transaction queue or new block processor.
        # If another masternode has transactions, it will send use a new block notification.
        # If we have transactions, we will do the opposite. This 'wakes' up the network.
        mn_logger.debug('Waiting for work or blocks...')
        while len(self.tx_batcher.queue) <= 0 and len(self.new_block_processor.q) <= 0:
            if not self.running:
                return

            await asyncio.sleep(0)
        mn_logger.debug('Work / blocks available. Continuing.')

    async def broadcast_new_blockchain_started(self):
        # Check if it was us who recieved the first transaction.
        # If so, multicast a block notification to wake everyone up
        mn_logger.debug('Sending new blockchain started signal.')
        if len(self.tx_batcher.queue) > 0:
            await router.secure_multicast(
                msg=get_genesis_block(),
                service=base.NEW_BLOCK_SERVICE,
                cert_dir=self.socket_authenticator.cert_dir,
                wallet=self.wallet,
                peer_map={
                    **self.get_delegate_peers(),
                    **self.get_masternode_peers()
                },
                ctx=self.ctx
            )

    async def new_blockchain_boot(self):
        self.log.info('Fresh blockchain boot.')

        # Simply wait for the first transaction to come through
        await self.hang()
        await self.broadcast_new_blockchain_started()

        while self.running:
            await self.loop()

    async def wait_for_block(self):
        self.new_block_processor.clean(self.current_height)

        while len(self.new_block_processor.q) <= 0:
            if not self.running:
                return
            await asyncio.sleep(0)

        block = self.new_block_processor.q.pop(0)
        self.process_new_block(block)

    async def join_quorum(self):
        # Catchup with NBNs until you have work, the join the quorum
        self.log.info('Join Quorum')

        # await self.intermediate_catchup()
        #
        # await self.hang()
        # await self.wait_for_block()

        members = self.driver.get_var(contract='masternodes', variable='S', arguments=['members'], mark=False)

        if len(members) > 1:
            while len(self.new_block_processor.q) <= 0:
                if not self.running:
                    return
                await asyncio.sleep(0)

            block = self.new_block_processor.q.pop(0)
            self.process_new_block(block)
            self.new_block_processor.clean(self.current_height)

        while self.running:
            await self.loop()

    async def send_work(self):
        # Hangs until upgrade is done
        while self.upgrade_manager.upgrade:
            await asyncio.sleep(0)

        # Else, batch some more txs
        self.log.info(f'Sending {len(self.tx_batcher.queue)} transactions.')

        tx_batch = self.tx_batcher.pack_current_queue()

        input_hash = tx_batch['input_hash']

        self.log.info(f'TX BATCH: {tx_batch}')

        # LOOK AT SOCKETS CLASS
        if len(self.get_delegate_peers()) == 0:
            self.log.error('No one online!')
            return False

        await router.secure_multicast(
            msg=tx_batch,
            service=base.WORK_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_delegate_peers(),
            ctx=self.ctx
        )

        return input_hash

    async def get_work_processed(self):
        await asyncio.sleep(1)

        input_hash = await self.send_work()

        # this really should just give us a block straight up
        masters = self.driver.get_var(contract='masternodes', variable='S', arguments=['members'], mark=False)

        self.log.info('=== ENTERING BUILD NEW BLOCK STATE ===')

        block = await self.aggregator.gather_subblocks(
            total_contacts=len(self.get_delegate_peers()),
            expected_subblocks=len(masters),
            current_height=self.current_height,
            current_hash=self.current_hash,
            input_hash=input_hash
        )

        original_block = copy.deepcopy(block)

        self.process_new_block(block)

        self.new_block_processor.clean(self.current_height)

        return original_block

    async def loop(self):
        self.log.info('=== ENTERING SEND WORK STATE ===')
        self.upgrade_manager.version_check(constitution=self.make_constitution())

        block = await self.get_work_processed()

        await router.secure_multicast(
            msg=block,
            service=base.NEW_BLOCK_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_delegate_peers(),
            ctx=self.ctx
        )

        await self.hang()

        await router.secure_multicast(
            msg=block,
            service=base.NEW_BLOCK_SERVICE,
            cert_dir=self.socket_authenticator.cert_dir,
            wallet=self.wallet,
            peer_map=self.get_masternode_peers(),
            ctx=self.ctx
        )

        # self.aggregator.sbc_inbox.q.clear()

    def stop(self):
        super().stop()
        self.router.socket.close()
        self.webserver.coroutine.result().close()


def get_genesis_block():
    block = {
        'hash': (b'\x00' * 32).hex(),
        'number': 0,
        'previous': (b'\x00' * 32).hex(),
        'subblocks': []
    }
    return block


