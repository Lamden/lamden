from contracting.db.driver import ContractDriver, Driver
from contracting.db.encoder import decode
from cilantro_ee.logger.base import get_logger

BLOCK_HASH_KEY = '_current_block_hash'
BLOCK_NUM_KEY = '_current_block_num'
NONCE_KEY = '__n'
PENDING_NONCE_KEY = '__pn'

log = get_logger('STATE')


class NonceDriver:
    def __init__(self, driver=Driver(collection='nonces'), pending=Driver(collection='pending_nonces')):
        self.driver = driver
        self.pending = pending

    @staticmethod
    def n_key(processor, sender):
        return ':'.join([processor.hex(), sender.hex()])

    def get_pending_nonce(self, processor: bytes, sender: bytes):
        return self.pending.get(self.n_key(processor, sender))

    def get_nonce(self, processor: bytes, sender: bytes):
        return self.driver.get(self.n_key(processor, sender))

    def set_pending_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.pending.set(self.n_key(processor, sender), nonce)

    def set_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.driver.set(self.n_key(processor, sender), nonce)

    def delete_pending_nonce(self, processor: bytes, sender: bytes):
        self.pending.delete(self.n_key(processor, sender))

    def get_latest_nonce(self, processor:bytes, sender: bytes):
        nonce = self.get_pending_nonce(processor, sender)

        if nonce is None:
            nonce = self.get_nonce(processor, sender)

        if nonce is None:
            nonce = 0

        return nonce

    def commit_nonces(self, nonce_hash=None):
        # Delete pending nonces and update the nonces
        if nonce_hash is not None:
            for k, v in nonce_hash.items():
                processor, sender = k

                self.set_nonce(processor=processor, sender=sender, nonce=v)
                self.delete_pending_nonce(processor=processor, sender=sender)
        else:
            # Commit all pending nonces straight up
            for n in self.driver.iter(PENDING_NONCE_KEY):
                _, processor, sender = n.split(':')

                processor = bytes.fromhex(processor)
                sender = bytes.fromhex(sender)

                nonce = self.get_pending_nonce(processor=processor, sender=sender)

                self.set_nonce(processor=processor, sender=sender, nonce=nonce)
                self.driver.delete(n)

    def delete_pending_nonces(self):
        for nonce in self.driver.keys(PENDING_NONCE_KEY):
            self.driver.delete(nonce)


class BlockchainDriver(ContractDriver):
    def get_latest_block_hash(self):
        block_hash = self.driver.get(BLOCK_HASH_KEY)
        if block_hash is None:
            return '0' * 64
        return block_hash

    def set_latest_block_hash(self, v: str):
        if type(v) == bytes:
            v = v.hex()
        assert len(v) == 64, 'Hash provided is not 32 bytes.'
        self.driver.set(BLOCK_HASH_KEY, v)

    latest_block_hash = property(get_latest_block_hash, set_latest_block_hash)

    def get_latest_block_num(self) -> int:
        num = self.driver.get(BLOCK_NUM_KEY)

        if num is None:
            return 0

        num = int(num)

        return num

    def set_latest_block_num(self, v):
        v = int(v)
        assert v >= 0, 'Block number must be positive integer.'

        # v = str(v).encode()

        self.driver.set(BLOCK_NUM_KEY, v)

    latest_block_num = property(get_latest_block_num, set_latest_block_num)

    def set_transaction_data(self, tx):
        if tx['state'] is not None and len(tx['state']) > 0:
            for delta in tx['state']:
                self.set(delta['key'], decode(delta['value']))
                log.info(f"{delta['key']} -> {decode(delta['value'])}")

    def update_with_block(self, block):
        if self.latest_block_hash != block['previous']:
            log.error('BLOCK MISMATCH!!!')

        self.latest_block_num += 1

        for sb in block['subBlocks']:
            for tx in sb['transactions']:
                self.set_transaction_data(tx=tx)

        # Commit new nonces
        self.commit_nonces()
        self.delete_pending_nonces()

        # Update our block hash and block num
        self.set_latest_block_hash(block['hash'])

    @staticmethod
    def n_key(key, processor, sender):
        return ':'.join([key, processor.hex(), sender.hex()])

    # Nonce methods
    def get_pending_nonce(self, processor: bytes, sender: bytes):
        return self.driver.get(self.n_key(PENDING_NONCE_KEY, processor, sender))

    def get_nonce(self, processor: bytes, sender: bytes):
        return self.driver.get(self.n_key(NONCE_KEY, processor, sender))

    def set_pending_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.driver.set(self.n_key(PENDING_NONCE_KEY, processor, sender), nonce)

    def set_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.driver.set(self.n_key(NONCE_KEY, processor, sender), nonce)

    def delete_pending_nonce(self, processor: bytes, sender: bytes):
        self.driver.delete(self.n_key(PENDING_NONCE_KEY, processor, sender))

    def get_latest_nonce(self, processor:bytes, sender: bytes):
        nonce = self.get_pending_nonce(processor, sender)

        if nonce is None:
            nonce = self.get_nonce(processor, sender)

        if nonce is None:
            nonce = 0

        return nonce

    def commit_nonces(self):
        for n in self.driver.iter(PENDING_NONCE_KEY):
            _, processor, sender = n.split(':')

            processor = bytes.fromhex(processor)
            sender = bytes.fromhex(sender)

            nonce = self.get_pending_nonce(processor=processor, sender=sender)

            self.set_nonce(processor=processor, sender=sender, nonce=nonce)
            self.delete(n, mark=False)

        self.commit()

    def delete_pending_nonces(self):
        for nonce in self.keys(PENDING_NONCE_KEY):
            self.delete(nonce, mark=False)

        self.commit()

    def iter(self, *args, **kwargs):
        return self.driver.iter(*args, **kwargs)