import asyncio
import hashlib
import time
from lamden.nodes.processors.processor import Processor
from lamden.crypto.wallet import Wallet
from lamden.storage import BlockStorage, get_latest_block_height
from lamden.nodes.filequeue import FileQueue
from lamden.formatting import primatives
from lamden.nodes import base
from contracting.db.driver import ContractDriver
from contracting.db.encoder import decode
import copy
from lamden.logger.base import get_logger

mn_logger = get_logger('Masternode')

BLOCK_SERVICE = 'service'
WORK_SERVICE = 'work'


class BlockService(Processor):
    def __init__(self, blocks: BlockStorage=None, driver=None):
        self.blocks = blocks
        self.driver = driver if driver is not None else ContractDriver()

    async def process_message(self, msg):
        response = None
        # mn_logger.debug('Got a msg')
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
            return {"error": "block does not exist"}

        return block


class TransactionBatcher:
    def __init__(self, wallet: Wallet, queue=None):
        self.wallet = wallet
        self.queue = queue if queue is not None else FileQueue()

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
        super().__init__(*args, **kwargs)
        # Services
        self.webserver_port = webserver_port
        self.upgrade_manager.webserver_port = self.webserver_port
        self.upgrade_manager.node_type = 'masternode'

        # Network upgrade flag
        self.active_upgrade = False

    def start_node(self):
        asyncio.ensure_future(self.start())

    async def start(self):
        # self.router.add_service(base.BLOCK_SERVICE, BlockService(self.blocks, self.driver))

        await super().start()

        asyncio.ensure_future(self.check_tx_queue())

        self.driver.clear_pending_state()

        if self.started:
            self.log.info('Done starting...')

    async def join_quorum(self):
        # Catchup with NBNs until you have work, the join the quorum
        self.log.info('Join Quorum')

        # await self.intermediate_catchup()
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

        # while self.running:
            # await self.loop()

def get_genesis_block():
    block = {
        'hash': (b'\x00' * 32).hex(),
        'number': 0,
        'previous': (b'\x00' * 32).hex(),
        'subblocks': []
    }
    return block

