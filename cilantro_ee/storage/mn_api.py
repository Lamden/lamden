from cilantro_ee.storage.master import DistributedMasterStorage
from cilantro_ee.logger.base import get_logger
from cilantro_ee.messages.block_data.block_data import BlockData
from bson.objectid import ObjectId
from collections import defaultdict
from typing import List
from cilantro_ee.messages.block_data.sub_block import SubBlock
from cilantro_ee.constants.system_config import *
import cilantro_ee

REPLICATION = 3             # TODO hard coded for now needs to change
GENESIS_HASH = '0' * 64
OID = '5bef52cca4259d4ca5607661'


class CilantroStorageDriver(DistributedMasterStorage):
    def __init__(self, key, distribute_writes=False, config_path=cilantro_ee.__path__[0], vkbook=PhoneBook):
        self.state_id = ObjectId(OID)
        self.log = get_logger("StorageDriver")

        self.block_index_delta = defaultdict(dict)
        self.send_req_blk_num = 0

        super().__init__(key, distribute_writes=distribute_writes, config_path=config_path, vkbook=vkbook)

    def store_block(self, sub_blocks: List[SubBlock]):
        last_block = self.get_last_n(1, DistributedMasterStorage.INDEX)[0]

        last_hash = last_block.get('blockHash')
        current_block_num = last_block.get('blockNum') + 1

        roots = [subblock.merkle_root for subblock in sub_blocks]

        block_hash = BlockData.compute_block_hash(roots, last_hash)

        if not self.distribute_writes:
            block_data = BlockData.create(block_hash, last_hash, PhoneBook.masternodes, current_block_num, sub_blocks)

        successful_storage = self.evaluate_wr(entry=block_data._data.to_dict())

        assert successful_storage is None or successful_storage is True, 'Write failure.'

        block_data._data.blockOwners = self.get_owners(block_hash)

        return block_data

    def get_transactions(self, tx_hash):
        txs = self.get_tx(tx_hash)

        if txs is None:
            return None

        block_num = txs.get('block')
        leaf = txs.get('tx_leaf')

        block = self.get_block(block_num)
        sub_blocks = block.get('subBlocks')

        for i in range(0, NUM_SB_PER_BLOCK):
            leaves = sub_blocks[i].get('merkleLeaves')

            try:
                tx_idx = leaves.index(leaf)
            except ValueError:
                tx_idx = -1

            if tx_idx >= 0:
                tx_dump = sub_blocks[i].get('transactions')
                return tx_dump[tx_idx]

        return None