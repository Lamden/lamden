from cilantro.storage.mongo import MDB
from cilantro.protocol import wallet
from cilantro.storage.vkbook import VKBook
from cilantro.nodes.masternode.master_store import MasterOps
# from cilantro.nodes.catchup import CatchupManager
from cilantro.storage.state import StateDriver
from cilantro.logger.base import get_logger
from cilantro.messages.block_data.block_data import BlockData, BlockMetaData
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
import dill, ujson as json, textwrap, bson
from bson.objectid import ObjectId
from collections import defaultdict
from typing import List
from cilantro.utils import Hasher
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.data import TransactionData

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
    def store_block(cls, merkle_roots=None, verifying_key=None, sign_key=None, transactions=None, input_hashes=None):
        """
        Triggered after 2/3rd consensus we create block and store to permanent storage

        :param merkle_roots:
        :param verifying_key:   vk for master
        :param sign_key:        sk for master
        :param transactions:
        :param input_hashes:
        :return:
        """
        prev_block_hash = cls.get_latest_block_hash()
        cls.log.important("store_block_new - prv block hash - {}".format(prev_block_hash))
        block_hash = BlockData.compute_block_hash(sbc_roots=merkle_roots, prev_block_hash=prev_block_hash)
        blk_num = MasterOps.get_blk_num_frm_blk_hash(blk_hash = prev_block_hash) + 1
        sig = MerkleSignature.create(sig_hex = wallet.sign(sign_key, block_hash.encode()),
                                     sender = verifying_key, timestamp = str(time.time()))

        block_data = BlockData.create(block_hash = block_hash, prev_block_hash = prev_block_hash,
                                      transactions = transactions, masternode_signature = sig,
                                      merkle_roots = merkle_roots, input_hashes = input_hashes, block_num = blk_num)

        block_dict = MDB.get_dict(block_data)
        assert (bool(MasterOps.evaluate_wr(entry=block_dict))) is True, "wr to master store failed, dump blk {}"\
            .format(block_dict)
        return block_data

    @classmethod
    def get_transactions(cls, block_hash=None, raw_tx_hash=None, status=None):
        # TODO verify
        pass

    '''
        api returns full block if stored locally else would return list of Master nodes responsible for it
    '''
    @classmethod
    def get_nth_full_block(cls, give_blk=None, mn_vk=None):
        """
        API gets request for block num, this api assumes requested block is stored locally
        else asserts

        :param give_blk: block num on chain
        :param mn_vk:    requester's vk
        :return:         None for incorrect, only full blk if block found else assert
        """

        valid_mn_id = VKBook.get_masternodes().index(mn_vk)
        if valid_mn_id is None:
            return None

        # check my index if my vk is listed in idx
        idx_entry = MasterOps.get_blk_idx(n_blks=give_blk)

        for key in idx_entry.get('mn_blk_owners'):
            if key == mn_vk:
                blk_entry = MasterOps.get_full_blk(blk_num = idx_entry.get('blockNum'))
                return blk_entry

        # assert isinstance(blk_entry), "fn get_nth_full_block failed to return blk {} for index".format(blk_entry,
        #                                                                                                idx_entry)

    @classmethod
    def get_latest_block_hash(cls):
        """
        looks up mn_index returns latest hash

        :return: block hash of last block on block chain
        """
        idx_entry = MasterOps.get_blk_idx(n_blks=1)
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
        return bool(MasterOps.get_blk_num_frm_blk_hash(block_hash))

    @classmethod
    def process_catch_up_idx(cls, vk=None, curr_blk_hash=None):
        """
        API gets latest hash requester has and responds with delta block index

        :param vk: mn or dl verifying key
        :param curr_blk_hash:
        :return:
        """

        # check if requester is master or del

        valid_node = bool(VKBook.get_masternodes().index(vk)) & bool(VKBook.get_delegates().index(vk))

        if valid_node is True:
            given_blk_num = MasterOps.get_blk_num_frm_blk_hash(blk_hash = curr_blk_hash)
            latest_blk = MasterOps.get_blk_idx(n_blks = 1)
            latest_blk_num = latest_blk.get('blockNum')

            if given_blk_num == latest_blk_num:
                cls.log.debug('given block is already latest')
                return None
            else:
                idx_delta = MasterOps.get_blk_idx(n_blks = (latest_blk_num - given_blk_num))
                return idx_delta

        assert valid_node is True, "invalid vk given key is not of master or delegate dumpting vk {}".format(vk)

    @classmethod
    def process_received_idx(cls, blk_idx_dict=None):
        """
        API goes list dict and sends out blk req for each blk num
        :param blk_idx_dict:
        :return:
        """
        last_elm_curr_list = sorted(cls.block_index_delta.keys())[-1]
        last_elm_new_list = sorted(blk_idx_dict.keys())[-1]

        if last_elm_curr_list > last_elm_new_list:
            cls.log.critical("incoming block delta is stale ignore continue wrk on old")
            return

        if last_elm_curr_list == last_elm_new_list:
            cls.log.info("delta is same returning")
            return
                  
        if last_elm_curr_list < last_elm_new_list:
            cls.log.critical("we have stale list update working list ")
            cls.block_index_delta = blk_idx_dict
            last_elm_curr_list = last_elm_new_list

        while cls.send_req_blk_num < last_elm_curr_list:
            # look for active master in vk list
            avail_copies = len(cls.block_index_delta[cls.send_req_blk_num])
            if avail_copies < REPLICATION:
                cls.log.critical("block is under protected needs to re protect")

            while avail_copies > 0:
                vk = cls.block_index_delta[cls.send_req_blk_num][avail_copies - 1]
                if vk in VKBook.get_masternodes():
                    CatchupManager._send_block_data_req(mn_vk = vk, req_blk_num = cls.send_req_blk_num)
                    break
                avail_copies = avail_copies - 1  # decrement count check for another master

            cls.send_req_blk_num += 1
            # TODO we should somehow check time out for these requests

    @classmethod
    def process_received_block(cls, block=None):
        block_dict = MDB.get_dict(block)
        update_blk_result = bool(MasterOps.evaluate_wr(entry=block_dict))
        assert update_blk_result is True, "failed to update block"


