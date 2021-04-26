import asyncio
import hashlib
import time
from lamden import router
from lamden.crypto.wallet import Wallet
from lamden.storage import BlockStorage, get_latest_block_height
from lamden.nodes.masternode import contender, webserver
from lamden.formatting import primatives
from lamden.nodes import base
from contracting.db.driver import ContractDriver

from lamden.logger.base import get_logger

mn_logger = get_logger('Masternode')

BLOCK_SERVICE = 'service'
WORK_SERVICE = 'work'


class BlockService(router.Processor):
    def __init__(self, blocks: BlockStorage=None, driver=ContractDriver()):
        self.blocks = blocks
        self.driver = driver

    async def process_message(self, msg):
        response = None
        mn_logger.debug('Got a msg')
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
    def __init__(self, wallet: Wallet, queue):
        self.wallet = wallet
        self.queue = queue

    def make_batch(self, transactions):
        timestamp = int(time.time())

        h = hashlib.sha3_256()
        h.update('{}'.format(timestamp).encode())
        input_hash = h.hexdigest()

        signature = self.wallet.sign(input_hash)

        batch = {
            'transactions': transactions,
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

    def get_next_tx_in_queue(self):
        return self.queue.pop(0)


class Masternode(base.Node):
    def __init__(self, webserver_port=8080, *args, **kwargs):
        super().__init__(store=True, *args, **kwargs)
        # Services
        self.webserver_port = webserver_port
        self.webserver = webserver.WebServer(
            work_processor=self.work_processor,
            contracting_client=self.client,
            driver=self.driver,
            blocks=self.blocks,
            wallet=self.wallet,
            port=self.webserver_port
        )
        self.upgrade_manager.webserver_port = self.webserver_port
        self.upgrade_manager.node_type = 'masternode'

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

        # Start the webserver to accept transactions
        await self.webserver.start()

        self.log.info('Done starting...')
        self.log.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! I'M NEW !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

        # If we have no blocks in our database, we are starting a new network from scratch

        asyncio.ensure_future(self.new_blockchain_boot())

        self.log.debug('returned')

    '''
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
    '''
    async def new_blockchain_boot(self):
        self.log.info('Fresh blockchain boot.')

        while self.running:
            await self.loop()
    '''
    async def wait_for_block(self):
        self.new_block_processor.clean(self.current_height)

        while len(self.new_block_processor.q) <= 0:
            if not self.running:
                return
            await asyncio.sleep(0)

        block = self.new_block_processor.q.pop(0)
        self.process_new_block(block)
    '''
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


