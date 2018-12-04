from cilantro.storage.mongo import MDB
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.messages.block_data.block_data import BlockData, BlockMetaData
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
import dill, ujson as json, textwrap, bson
from bson.objectid import ObjectId
from typing import List
from cilantro.utils import Hasher
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.messages.transaction.data import TransactionData

GENESIS_HASH = '0' * 64
OID = '5bef52cca4259d4ca5607661'


class StorageDriver:
    """
    APIs for BlockStorage. This class should only be used by Masternodes, since it interfaces with MongoDB.
    Note: If a Delegate/Witness needs to get_latest_block_hash, they should use StateDriver instead.
    """

    state_id = ObjectId(OID)

    @classmethod
    def store_block(cls, block: BlockData, validate: bool=False):
        if validate:
            block.validate()

        block_dict = MDB.get_dict(block)
        return bool(MasterOps.evaluate_wr(entry=block_dict))

    @classmethod
    def get_transactions(cls, block_hash=None, raw_tx_hash=None, status=None):
        # TODO verify
        pass
        # assert block_hash or raw_tx_hash or status, 'Must provide at least one search criteria'
        # query = {}
        # if block_hash:
        #     query['block_hash'] = block_hash
        # if raw_tx_hash:
        #     query['raw_tx_hash'] = raw_tx_hash
        # if status:
        #     query['status'] = status
        # return MDB.mn_db['transactions'].find(query)

    '''
        api returns full block if stored locally else would return list of Master nodes responsible for
        it
    '''
    @classmethod
    def get_latest_block(cls, my_key=None):
        idx_entry = MasterOps.get_blk_idx(n_blks=1, my_key=my_key)

        for key in idx_entry.get('master_nodes'):
            if key == my_key:
                blk_entry = MasterOps.get_full_blk(blk_num = idx_entry.get('blockNum'))
                return blk_entry

        # return idx entry if blk is not stored locally
        return idx_entry

    @classmethod
    def get_latest_block_hash(cls):
        idx_entry = MasterOps.get_blk_idx(n_blk=1)
        blk_hash = idx_entry.get('blockHash')
        print("######")
        print(blk_hash)
        return blk_hash

    @classmethod
    def catch_me_up(cls, node_type=None, my_blk_hash=None):
        if node_type is 'mn':
            given_blk_num = MasterOps.get_blk_num_frm_blk_hash(blk_hash = my_blk_hash)
            latest_blk = MasterOps.get_blk_idx(n_blks = 1)
            latest_blk_num = latest_blk.get('blockNum')

            if given_blk_num == latest_blk_num:
                cls.log.debug('given block is already latest')
                return None
            else:
                idx_delta = MasterOps.get_blk_idx(n_blks = (latest_blk_num - given_blk_num))
                return idx_delta

        if node_type is 'dn':
            # TODO
            pass
