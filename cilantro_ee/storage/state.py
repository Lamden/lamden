from cilantro_ee.logger.base import get_logger
from cilantro_ee.constants import conf
from contracting.db.driver import RocksDriver
from contracting.db import encoder

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
        super().set(key, value)

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

    def get_latest_block_num(self):
        num = self.get(self.block_num_key)

        if num is None:
            return 0

        num = int(num)

        return num

    def set_latest_block_num(self, v):
        v = int(v)
        assert v >= 0, 'Block number must be positive integer.'

        v = str(v).encode()

        self.set(self.block_num_key, v)

    latest_block_num = property(get_latest_block_num, set_latest_block_num)

    def set_transaction_data(self, tx):
        if tx['state'] is not None and len(tx['state']) > 0:
            for delta in tx['state']:
                self.set(delta['key'], delta['value'])

    def update_with_block(self, block, commit_tx=True):
        self.log.info('UPDATING STATE')

        # Capnp proto shim until we remove it completely from storage
        if type(block) != dict:
            block = block.to_dict()

        # self.log.info("block {}".format(block))

        if self.latest_block_hash != block['prevBlockHash']:
            return

        # Map of tuple to nonce such that (processor, sender) => nonce
        nonces = {}

        for sb in block['subBlocks']:
            if type(sb) != dict:
                sb = sb.to_dict()
            for tx in sb['transactions']:
                self.nonce_manager.update_nonce_hash(nonce_hash=nonces, tx_payload=tx['transaction']['payload'])
                if commit_tx:
                    self.set_transaction_data(tx=tx)

        # Commit new nonces
        self.nonce_manager.commit_nonces(nonce_hash=nonces)
        self.nonce_manager.delete_pending_nonces()

        # Update our block hash and block num
        self.set_latest_block_hash(block['blockHash'])
        self.set_latest_block_num(block['blockNum'])
