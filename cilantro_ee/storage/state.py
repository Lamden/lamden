from cilantro_ee.logger.base import get_logger
import json

from contracting.db.driver import DatabaseDriver
from contracting.db import encoder


class MetaDataStorage(DatabaseDriver):
    def __init__(self, block_hash_key='_current_block_hash', block_num_key='_current_block_num', nonce_key='__n',
                 pending_nonce_key='__pn'):

        self.block_hash_key = block_hash_key
        self.block_num_key = block_num_key
        self.log = get_logger('StateDriver')
        self.interface = None

        self.nonce_key = nonce_key
        self.pending_nonce_key = pending_nonce_key

        super().__init__()

    def get(self, key):
        value = super().get(key)
        return encoder.decode(value)

    def set(self, key, value):
        v = encoder.encode(value)
        super().set(key, v)

    def raw_set(self, key, value):
        super().set(key, value)

    def update_with_block(self, block):
        self.log.success('UPDATING STATE')

        # Map of tuple to nonce such that (processor, sender) => nonce
        nonces = {}

        for sb in block.subBlocks:
            for tx in sb.transactions:

                # Get the current nonce stored
                current_nonce = nonces.get((tx.transaction.payload.processor, tx.transaction.payload.sender))

                # If no nonce has been stored, or the one stored is less than the one in the new transaction,
                # set it to the new transaction's nonce
                if current_nonce is None or current_nonce < tx.transaction.payload.nonce:
                    nonces[(tx.transaction.payload.processor, tx.transaction.payload.sender)] = \
                    tx.transaction.payload.nonce

                # If there are state effects in the transaction, try setting them by loading the JSON
                if tx.state is not None and len(tx.state) > 0:
                    try:
                        sets = json.loads(tx.state)

                        # For each KV in the JSON, set the key to the value
                        for k, v in sets.items():
                            self.log.info('SETTING "{}" to "{}"'.format(k, v))

                            # Not sure if this should be encoded or not...
                            self.raw_set(k, v)
                    except Exception as e:
                        # Log exceptions
                        self.log.critical(str(e))

        # Delete pending nonces and update the nonces
        for k, v in nonces.items():
            processor, sender = k
            self.set_nonce(processor=processor, sender=sender, nonce=v)
            self.delete_pending_nonce(processor=processor, sender=sender)

        # Update our block hash and block num
        self.latest_block_hash = block.blockHash
        self.latest_block_num = block.blockNum

        #self.log.info('Processed block #{} with hash {}.'.format(self.latest_block_num, self.latest_block_hash))

        assert self.latest_block_hash == block.blockHash, \
            "StateUpdate failed! Latest block hash {} does not match block data {}".format(self.latest_block_hash, block)

    def get_latest_block_hash(self):
        block_hash = self.get(self.block_hash_key)
        if block_hash is None:
            return b'\x00' * 32
        return bytes.fromhex(block_hash)

    def set_latest_block_hash(self, v: bytes):
        if type(v) == str:
            v = bytes.fromhex(v)
        assert len(v) == 32, 'Hash provided is not 32 bytes.'
        self.set(self.block_hash_key, v)

    latest_block_hash = property(get_latest_block_hash, set_latest_block_hash)

    def get_latest_block_num(self):
        num = self.get(self.block_num_key)
        if num is None:
            return 0

        return num

    def set_latest_block_num(self, v):
        v = int(v)
        assert v >= 0, 'Block number must be positive integer.'
        self.set(self.block_num_key, v)

    latest_block_num = property(get_latest_block_num, set_latest_block_num)

    @staticmethod
    def nonce_key(key, processor, sender):
        return ':'.join([key, processor.hex(), sender.hex()])

    # Nonce methods
    def get_pending_nonce(self, processor: bytes, sender: bytes):
        nonce = self.get(':'.join([self.pending_nonce_key, processor.hex(), sender.hex()]))
        return encoder.decode(nonce)

    def get_nonce(self, processor: bytes, sender: bytes):
        nonce = self.get(':'.join([self.nonce_key, processor.hex(), sender.hex()]))
        return encoder.decode(nonce)

    def set_pending_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.set(':'.join([self.pending_nonce_key, processor.hex(), sender.hex()]), encoder.encode(nonce))

    def set_nonce(self, processor: bytes, sender: bytes, nonce: int):
        self.set(':'.join([self.nonce_key, processor.hex(), sender.hex()]), encoder.encode(nonce))

    def delete_pending_nonce(self, processor: bytes, sender: bytes):
        self.delete(':'.join([self.pending_nonce_key, processor.hex(), sender.hex()]))