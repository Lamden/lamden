from contracting.db.driver import ContractDriver

BLOCK_HASH_KEY = '_current_block_hash'
BLOCK_NUM_KEY = '_current_block_num'
NONCE_KEY = '__n'
PENDING_NONCE_KEY = '__pn'

from cilantro_ee.logger.base import get_logger

log = get_logger('STATE')


class BlockchainDriver(ContractDriver):
    def get_latest_block_hash(self):
        block_hash = super().get_direct(BLOCK_HASH_KEY)
        if block_hash is None:
            return b'\x00' * 32
        return block_hash

    def set_latest_block_hash(self, v: bytes):
        if type(v) == str:
            v = bytes.fromhex(v)
        assert len(v) == 32, 'Hash provided is not 32 bytes.'
        super().set_direct(BLOCK_HASH_KEY, v)

    latest_block_hash = property(get_latest_block_hash, set_latest_block_hash)

    def get_latest_block_num(self):
        num = super().get_direct(BLOCK_NUM_KEY)

        if num is None:
            return 0

        num = int(num)

        return num

    def set_latest_block_num(self, v):
        v = int(v)
        assert v >= 0, 'Block number must be positive integer.'

        v = str(v).encode()

        super().set_direct(BLOCK_NUM_KEY, v)

    latest_block_num = property(get_latest_block_num, set_latest_block_num)

    def set_transaction_data(self, tx):
        if tx['state'] is not None and len(tx['state']) > 0:
            for delta in tx['state']:
                self.set(delta['key'], delta['value'])
                log.info(f"{delta['key']} -> {delta['value']}")

    def update_with_block(self, block, commit_tx=True):
        # Capnp proto shim until we remove it completely from storage
        if type(block) != dict:
            block = block.to_dict()

        self.set_latest_block_num(block['blockNum'])

        # self.log.info("block {}".format(block))

        log.info(f'LATEST: {self.latest_block_hash}')
        log.info(f"PREV: {block['prevBlockHash']}")

        if self.latest_block_hash != block['prevBlockHash']:
            log.error('BLOCK MISMATCH!!!')
        #     return

        # Map of tuple to nonce such that (processor, sender) => nonce
        nonces = {}

        for sb in block['subBlocks']:
            if type(sb) != dict:
                sb = sb.to_dict()
            for tx in sb['transactions']:
                self.update_nonce_hash(nonce_hash=nonces, tx_payload=tx['transaction']['payload'])
                if commit_tx:
                    self.set_transaction_data(tx=tx)

        # Commit new nonces
        self.commit_nonces(nonce_hash=nonces)
        self.delete_pending_nonces()

        # Update our block hash and block num
        self.set_latest_block_hash(block['blockHash'])

    @staticmethod
    def update_nonce_hash(nonce_hash: dict, tx_payload):
        if type(tx_payload) != dict:
            tx_payload = tx_payload.to_dict()
        # Modifies the provided dict
        k = (tx_payload['processor'], tx_payload['sender'])
        current_nonce = nonce_hash.get(k)

        if current_nonce is None or current_nonce == tx_payload['nonce']:
            nonce_hash[k] = tx_payload['nonce'] + 1

    @staticmethod
    def n_key(key, processor, sender):
        return ':'.join([key, processor.hex(), sender.hex()])

    # Nonce methods
    def get_pending_nonce(self, processor: bytes, sender: bytes):
        return self.get(self.n_key(PENDING_NONCE_KEY, processor, sender))

    def get_nonce(self, processor: bytes, sender: bytes):
        return self.get(self.n_key(NONCE_KEY, processor, sender))

    def set_pending_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.set(self.n_key(PENDING_NONCE_KEY, processor, sender), nonce)

    def set_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.set(self.n_key(NONCE_KEY, processor, sender), nonce)

    def delete_pending_nonce(self, processor: bytes, sender: bytes):
        self.delete(self.n_key(PENDING_NONCE_KEY, processor, sender))

    def commit_nonces(self, nonce_hash=None):
        # Delete pending nonces and update the nonces
        if nonce_hash is not None:
            for k, v in nonce_hash.items():
                processor, sender = k

                self.set_nonce(processor=processor, sender=sender, nonce=v)
                self.delete_pending_nonce(processor=processor, sender=sender)
        else:
            # Commit all pending nonces straight up
            for n in self.iter(PENDING_NONCE_KEY):
                _, processor, sender = n.split(':')

                processor = bytes.fromhex(processor)
                sender = bytes.fromhex(sender)

                nonce = self.get_pending_nonce(processor=processor, sender=sender)

                self.set_nonce(processor=processor, sender=sender, nonce=nonce)
                self.delete(n)

        self.commit()

    def delete_pending_nonces(self):
        for nonce in self.iter(PENDING_NONCE_KEY):
            self.delete(nonce)

        self.commit()

    def update_nonces_with_block(self, block):
        # Reinitialize the latest nonce. This should probably be abstracted into a seperate class at a later date
        nonces = {}

        for sb in block.subBlocks:
            for tx in sb.transactions:
                self.update_nonce_hash(nonce_hash=nonces, tx_payload=tx.transaction.payload)

        self.commit_nonces(nonce_hash=nonces)
        self.delete_pending_nonces()
