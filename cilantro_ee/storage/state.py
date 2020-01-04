from cilantro_ee.logger.base import get_logger
import json
from cilantro_ee.constants import conf
from contracting.db.driver import RocksDriver
from contracting.db import encoder

import contextlib

from cilantro_ee.core.nonces import NonceManager


class MetaDataStorage(RocksDriver):
    def __init__(self,
                 block_hash_key='_current_block_hash',
                 epoch_hash_key='_current_epoch_hash',
                 block_num_key='_current_block_num',
                 nonce_key='__n',
                 pending_nonce_key='__pn'):

        self.block_hash_key = block_hash_key
        self.epoch_hash_key = epoch_hash_key
        self.block_num_key = block_num_key
        self.log = get_logger('StateDriver')
        self.interface = None

        self.nonce_key = nonce_key
        self.pending_nonce_key = pending_nonce_key

        self.nonce_manager = NonceManager()

        super().__init__()

    def get(self, key):
        value = super().get(key)
        return encoder.decode(value)

    def set(self, key, value):
        v = encoder.encode(value)
        super().set(key, v)

    def get_latest_block_hash(self):
        block_hash = super().get(self.block_hash_key)
        if block_hash is None:
            return b'\x00' * 32
        return block_hash

    def set_latest_block_hash(self, v: bytes):
        if type(v) == str:
            v = bytes.fromhex(v)
        assert len(v) == 32, 'Hash provided is not 32 bytes.'
        super().set(self.block_hash_key, v)

    latest_block_hash = property(get_latest_block_hash, set_latest_block_hash)

    def get_latest_epoch_hash(self):
        epoch_hash = super().get(self.epoch_hash_key)
        if epoch_hash is None:
            return b'\x00' * 32
        return epoch_hash

    def set_latest_epoch_hash(self, v: bytes):
        if type(v) == str:
            v = bytes.fromhex(v)
        assert len(v) == 32, 'Hash provided is not 32 bytes.'
        super().set(self.epoch_hash_key, v)

    latest_epoch_hash = property(get_latest_epoch_hash, set_latest_epoch_hash)

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

    def set_transaction_data(self, tx):
        if tx['state'] is not None and len(tx['state']) > 0:
            with contextlib.suppress(json.JSONDecodeError):
                sets = json.loads(tx['state'])

            if type(sets) != dict:
                return

            # For each KV in the JSON, set the key to the value
            for k, v in sets.items():
                self.set(k, v)

    def update_with_block(self, block):
        self.log.success('UPDATING STATE')

        # Capnp proto shim until we remove it completely from storage
        if type(block) != dict:
            block = block.to_dict()

        # self.log.info("block {}".format(block))

        assert self.latest_block_hash == block['prevBlockHash'], \
            "StateUpdate failed! Latest block hash {} does not match block data {}".format(self.latest_block_hash, block)

        # Map of tuple to nonce such that (processor, sender) => nonce
        nonces = {}

        for sb in block['subBlocks']:
            if type(sb) != dict:
                sb = sb.to_dict()
            for tx in sb['transactions']:
                self.nonce_manager.update_nonce_hash(nonce_hash=nonces, tx_payload=tx['transaction']['payload'])
                self.set_transaction_data(tx=tx)

        # Commit new nonces
        self.nonce_manager.commit_nonces(nonce_hash=nonces)
        self.nonce_manager.delete_pending_nonces()

        # Update our block hash and block num
        self.latest_block_hash = block['blockHash']
        self.latest_block_num = block['blockNum']

        # Update the epoch hash if it is time
        if self.latest_block_num % conf.EPOCH_INTERVAL == 0:
            self.latest_epoch_hash = self.latest_block_hash

            # Update rewards
