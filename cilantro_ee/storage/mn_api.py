from cilantro_ee.nodes.masternode.master_store import MasterOps
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
        pass

class StorageDriver:

    @classmethod
    def get_transactions(cls, raw_tx_hash):

        map = MasterOps.get_usr_tx_result(usr_tx_hash = raw_tx_hash)

        if not map:
            return

        # identify Leaf and block num from given hash in map
        blk_num = map.get('block')
        leaf = map.get('tx_leaf')

        # get relevant block
        block = cls.get_nth_full_block(given_bnum = blk_num)
        sub_blk = block.get('subBlocks')

        # find leaf from sub block
        for i in range(0, NUM_SB_PER_BLOCK):
            leaves = sub_blk[i].get('merkleLeaves')
            try:
                tx_idx = leaves.index(leaf)
            except ValueError:
                tx_idx = -1

            if tx_idx >= 0:
                tx_dump = sub_blk[i].get('transactions')
                cls.log.spam("index {} leaves {} tx {}".format(tx_idx, leaves, tx_dump[tx_idx]))
                return tx_dump[tx_idx]

        return

    '''
        api returns full block if stored locally else would return list of Master nodes responsible for it
    '''
    @classmethod
    def get_nth_full_block(cls, given_bnum=None, given_hash=None):
        """
        API gets request for block num, this api assumes requested block is stored locally
        else asserts

        :param give_blk: block num on chain
        :param mn_vk:    requester's vk
        :return:         None for incorrect, only full blk if block found else assert
        """

        assert given_bnum is not None and given_hash is not None, 'Need block number or hash.'
        q = {'blockNum': given_bnum} if given_bnum is not None else {'blockHash': given_hash}

        full_block = GlobalColdStorage.driver.blocks.collection.find_one(q)

        if full_block is not None:
            full_block.pop('_id')
            return full_block
        else:
            # TODO anarchy net this wont be used
            blk_owners = MasterOps.get_blk_owners()
            return blk_owners


    @classmethod
    def get_latest_block_hash(cls):
        """
        looks up mn_index returns latest hash

        :return: block hash of last block on block chain
        """
        idx_entry = MasterOps.get_blk_idx(n_blks=1)[-1]
        cls.log.debug("get_latest_block_hash idx_entry -> {}".format(idx_entry))
        blk_hash = idx_entry.get('blockHash')
        cls.log.debug("get_latest_block_hash blk_hash ->{}".format(blk_hash))
        return blk_hash

    @classmethod
    def get_latest_block_num(cls):
        """
        looks up mn_index returns latest num

        :return: block num of last block on block chain
        """
        idx_entry = MasterOps.get_blk_idx(n_blks=1)[-1]
        cls.log.debug("get_latest_block_num idx_entry -> {}".format(idx_entry))
        blk_num = idx_entry.get('blockNum')
        cls.log.debug("get_latest_block_num blk_num ->{}".format(blk_num))
        return blk_num

    @classmethod
    def check_block_exists(cls, block_hash: str) -> bool:
        """
        Checks if the given block hash exists in our index table
        :param block_hash: The block hash to check
        :return: True if the block hash exists in our index table, and False otherwise
        """
        return GlobalColdStorage.driver.blocks.collection.find_one({
            'blockHash': block_hash
        }) is not None
