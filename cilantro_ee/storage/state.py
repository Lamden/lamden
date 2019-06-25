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

    def update_with_block(self, block: BlockData):
        for tx in block.transactions:
            assert tx.contract_type is ContractTransaction, "Expected contract tx but got {}".format(tx.contract_type)

            if tx.state is not None and len(tx.state) > 0:
                try:
                    sets = json.loads(tx.state)


                    for k, v in sets.items():
                        self.set(k, v)
                except:
                    pass
                    #self.log.info('Set {} to {}'.format(k, v))

        # Update our block hash and block num
        self.latest_block_hash = block.block_hash
        self.latest_block_num = block.block_num

        #self.log.info('Processed block #{} with hash {}.'.format(self.latest_block_num, self.latest_block_hash))

        assert self.latest_block_hash == block.block_hash, \
            "StateUpdate failed! Latest block hash {} does not match block data {}".format(self.latest_block_hash, block)

    def get_latest_block_hash(self):
        block_hash = self.get(self.block_hash_key)
        if block_hash is None:
            return '0' * 64
        return block_hash.decode()

    def set_latest_block_hash(self, v):
        print(type(v))
        assert len(v) == 64, 'Hash provided is not 64 characters.'
        int(v, 16)

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