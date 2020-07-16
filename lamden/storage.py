from contracting.db.driver import ContractDriver
from pymongo import MongoClient, DESCENDING

import lamden
from lamden.logger.base import get_logger

BLOCK_HASH_KEY = '_current_block_hash'
BLOCK_NUM_HEIGHT = '_current_block_height'
NONCE_KEY = '__n'
PENDING_NONCE_KEY = '__pn'

log = get_logger('STATE')


class NonceStorage:
    def __init__(self, port=27027, db_name='lamden', nonce_collection='nonces', pending_collection='pending_nonces', config_path=lamden.__path__[0]):
        self.config_path = config_path

        self.port = port

        self.client = MongoClient()
        self.db = self.client.get_database(db_name)
        self.nonces = self.db[nonce_collection]
        self.pending_nonces = self.db[pending_collection]

    @staticmethod
    def get_one(sender, processor, db):
        v = db.find_one(
            {
                'sender': sender,
                'processor': processor
            }
        )

        if v is None:
            return None

        return v['value']

    @staticmethod
    def set_one(sender, processor, value, db):
        db.update_one(
            {
                'sender': sender,
                'processor': processor
            },
            {
                '$set':
                    {
                        'value': value
                    }
            }, upsert=True
        )

    def get_nonce(self, sender, processor):
        return self.get_one(sender, processor, self.nonces)

    def get_pending_nonce(self, sender, processor):
        return self.get_one(sender, processor, self.pending_nonces)

    def set_nonce(self, sender, processor, value):
        self.set_one(sender, processor, value, self.nonces)

    def set_pending_nonce(self, sender, processor, value):
        self.set_one(sender, processor, value, self.pending_nonces)

    def get_latest_nonce(self, sender, processor):
        latest_nonce = self.get_pending_nonce(sender=sender, processor=processor)

        if latest_nonce is None:
            latest_nonce = self.get_nonce(sender=sender, processor=processor)

        if latest_nonce is None:
            latest_nonce = 0

        return latest_nonce

    def flush(self):
        self.nonces.drop()
        self.pending_nonces.drop()


def get_latest_block_hash(driver: ContractDriver):
    latest_hash = driver.get(BLOCK_HASH_KEY, mark=False)
    if latest_hash is None:
        return '0' * 64
    return latest_hash


def set_latest_block_hash(h, driver: ContractDriver):
    driver.driver.set(BLOCK_HASH_KEY, h)


def get_latest_block_height(driver: ContractDriver):
    h = driver.get(BLOCK_NUM_HEIGHT, mark=False)
    if h is None:
        return 0
    return h


def set_latest_block_height(h, driver: ContractDriver):
    driver.driver.set(BLOCK_NUM_HEIGHT, h)


def update_state_with_transaction(tx, driver: ContractDriver, nonces: NonceStorage):
    nonces_to_delete = []

    if tx['state'] is not None and len(tx['state']) > 0:
        for delta in tx['state']:
            driver.driver.set(delta['key'], delta['value'])
            log.debug(f"{delta['key']} -> {delta['value']}")

            nonces.set_nonce(
                sender=tx['transaction']['payload']['sender'],
                processor=tx['transaction']['payload']['processor'],
                value=tx['transaction']['payload']['nonce'] + 1
            )

            nonces_to_delete.append((tx['transaction']['payload']['sender'], tx['transaction']['payload']['processor']))

    for n in nonces_to_delete:
        nonces.set_pending_nonce(*n, value=None)


def update_state_with_block(block, driver: ContractDriver, nonces: NonceStorage):
    for sb in block['subblocks']:
        for tx in sb['transactions']:
            update_state_with_transaction(tx, driver, nonces)

    # Update our block hash and block num
    set_latest_block_hash(block['hash'], driver=driver)
    set_latest_block_height(block['number'], driver=driver)


class BlockStorage:
    BLOCK = 0
    TX = 1

    def __init__(self, port=27027, config_path=lamden.__path__[0], db='lamden', blocks_collection='blocks', tx_collection='tx'):
        # Setup configuration file to read constants
        self.config_path = config_path

        self.port = port

        self.client = MongoClient()
        self.db = self.client.get_database(db)

        self.blocks = self.db[blocks_collection]
        self.txs = self.db[tx_collection]

    def q(self, v):
        if isinstance(v, int):
            return {'number': v}
        return {'hash': v}

    def get_block(self, v=None):
        if v is None:
            return None

        q = self.q(v)
        block = self.blocks.find_one(q)

        if block is not None:
            block.pop('_id')

        return block

    def put(self, data, collection=BLOCK):
        if collection == BlockStorage.BLOCK:
            _id = self.blocks.insert_one(data)
            del data['_id']
        elif collection == BlockStorage.TX:
            _id = self.txs.insert_one(data)
            del data['_id']
        else:
            return False

        return _id is not None

    def get_last_n(self, n, collection=BLOCK):
        if collection == BlockStorage.BLOCK:
            c = self.blocks
        else:
            return None

        block_query = c.find({}, {'_id': False}).sort(
            'number', DESCENDING
        ).limit(n)

        blocks = [block for block in block_query]

        if len(blocks) > 1:
            first_block_num = blocks[0].get('number')
            last_block_num = blocks[-1].get('number')

            assert first_block_num > last_block_num, "Blocks are not descending."

        return blocks

    def get_tx(self, h):
        tx = self.txs.find_one({'hash': h})

        if tx is not None:
            tx.pop('_id')

        return tx

    def drop_collections(self):
        self.blocks.drop()
        self.txs.drop()

    def flush(self):
        self.drop_collections()

    def store_block(self, block):
        self.put(block, BlockStorage.BLOCK)
        self.store_txs(block)

    def store_txs(self, block):
        for subblock in block['subblocks']:
            for tx in subblock['transactions']:
                self.put(tx, BlockStorage.TX)
