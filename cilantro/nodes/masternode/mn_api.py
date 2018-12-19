from cilantro.storage.mongo import MDB
from cilantro.protocol import wallet
from cilantro.storage.vkbook import VKBook
from cilantro.nodes.masternode.master_store import MasterOps
# from cilantro.nodes.catchup import CatchupManager
from cilantro.storage.state import StateDriver
from cilantro.logger.base import get_logger
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
import dill, ujson as json, textwrap, bson
from bson.objectid import ObjectId
from collections import defaultdict
from typing import List
from cilantro.utils import Hasher
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.data import TransactionData
from cilantro.messages.block_data.sub_block import SubBlock

import time

REPLICATION = 3             # TODO hard coded for now needs to change
GENESIS_HASH = '0' * 64
OID = '5bef52cca4259d4ca5607661'


class StorageDriver:
    """
    APIs for BlockStorage. This class should only be used by Masternodes, since it interfaces with MongoDB.
    Note: If a Delegate/Witness needs to get_latest_block_hash, they should use StateDriver instead.
    """

    state_id = ObjectId(OID)
    log = get_logger("StorageDriver")

    block_index_delta = defaultdict(dict)
    send_req_blk_num = 0

    @classmethod
    def store_block(cls, sub_blocks: List[SubBlock]):
        """
        Triggered after 2/3rd consensus we create block and store to permanent storage
        """
        prev_block_hash = cls.get_latest_block_hash()
        blk_num = MasterOps.get_blk_num_frm_blk_hash(blk_hash=prev_block_hash) + 1
        roots = [sb.merkle_root for sb in sub_blocks]
        block_hash = BlockData.compute_block_hash(sbc_roots=roots, prev_block_hash=prev_block_hash)

        cls.log.important("Attempting to store block number {} with hash {} and previous hash {}"
                          .format(blk_num, block_hash, prev_block_hash))

        # TODO get actual block owners...
        block_data = BlockData.create(block_hash=block_hash, prev_block_hash=prev_block_hash, block_owners=[],
                                      block_num=blk_num, sub_blocks=sub_blocks)

        assert (bool(MasterOps.evaluate_wr(entry=block_data._data.to_dict()))) is True, "wr to master store failed, dump blk {}"\
            .format(block_data)

        # Attach the block owners data to the BlockData instance  TODO -- find better solution
        block_data._data.blockOwners = MasterOps.get_blk_owners(block_hash)

        return block_data

    @classmethod
    def get_transactions(cls, block_hash=None, raw_tx_hash=None, status=None):
        # TODO verify
        pass

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

        if given_bnum is not None:
            full_block = MasterOps.get_full_blk(blk_num=given_bnum)
            if full_block is not None:
                return full_block
            else:
                blk_owners = MasterOps.get_blk_owners()
                return blk_owners

        if given_hash is not None:
            full_block = MasterOps.get_full_blk(blk_hash=given_hash)
            if full_block is not None:
                return full_block
            else:
                blk_owners = MasterOps.get_blk_owners()
                return blk_owners

    @classmethod
    def get_latest_block_hash(cls):
        """
        looks up mn_index returns latest hash

        :return: block hash of last block on block chain
        """
        idx_entry = MasterOps.get_blk_idx(n_blks=1)[0]
        cls.log.debug("get_latest_block_hash idx_entry -> {}".format(idx_entry))
        blk_hash = idx_entry.get('blockHash')
        cls.log.debug("get_latest_block_hash blk_hash ->{}".format(blk_hash))
        return blk_hash

    @classmethod
    def check_block_exists(cls, block_hash: str) -> bool:
        """
        Checks if the given block hash exists in our index table
        :param block_hash: The block hash to check
        :return: True if the block hash exists in our index table, and False otherwise
        """
        return MasterOps.get_blk_num_frm_blk_hash(block_hash) is not None
