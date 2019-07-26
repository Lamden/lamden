from cilantro_ee.logger.base import get_logger
from cilantro_ee.messages.transaction.contract import ContractTransaction
from cilantro_ee.messages.block_data.block_data import BlockData
import json

from contracting.db.driver import DatabaseDriver


class MetaDataStorage(DatabaseDriver):
    def __init__(self, block_hash_key='_current_block_hash', block_num_key='_current_block_num'):
        self.block_hash_key = block_hash_key
        self.block_num_key = block_num_key
        self.log = get_logger('StateDriver')
        self.interface = None

        super().__init__()

    def update_with_block(self, block):
        for sb in block.subBlocks:
            for tx in sb.transactions:
                if tx.state is not None and len(tx.state) > 0:
                    try:
                        sets = json.loads(tx.state)

                        for k, v in sets.items():
                            self.log.info('SETTING "{}" to "{}"'.format(k, v))
                            self.set(k, v)
                    except Exception as e:
                        self.log.critical(str(e))

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
        return block_hash

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

        return int(num.decode())

    def set_latest_block_num(self, v):
        v = int(v)
        assert v >= 0, 'Block number must be positive integer.'
        self.set(self.block_num_key, v)

    latest_block_num = property(get_latest_block_num, set_latest_block_num)